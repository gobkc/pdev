#!/usr/bin/env python3
import os, json, subprocess, threading, datetime, shutil
from pathlib import Path
import tkinter as tk
from tkinter import ttk, scrolledtext, simpledialog, messagebox,filedialog

CONFIG_DIR = Path.home() / ".config" / "kdev"
CACHE_FILE = CONFIG_DIR / ".kdev.js"

def find_kubectl():
    """
    自动寻找 kubectl 可执行文件路径
    优先 /usr/local/bin, 再 /usr/bin, 再 PATH
    """
    # 先固定路径查找
    for path in ["/usr/local/bin/kubectl", "/usr/bin/kubectl"]:
        if os.path.isfile(path) and os.access(path, os.X_OK):
            return path
    # fallback: PATH 中查找
    kubectl = shutil.which("kubectl")
    if kubectl:
        return kubectl
    raise FileNotFoundError("kubectl 可执行文件未找到，请确认已安装")

def ensure_cache():
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    if not CACHE_FILE.exists():
        CACHE_FILE.write_text(json.dumps({}))

def load_cache():
    ensure_cache()
    try:
        return json.load(open(CACHE_FILE))
    except: return {}

def save_cache(data):
    with open(CACHE_FILE,"w") as f:
        json.dump(data,f,indent=2)

def cache_get(k):
    d = load_cache()
    return d.get(k,{}).get("value")

def cache_set(k,v):
    d = load_cache()
    d[k]={"ts":0,"value":v}
    save_cache(d)

def command_insert(cmd_area,msg):
    ts=datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cmd_area.insert(tk.END,f"{ts} {msg}\n")
    cmd_area.see(tk.END)
    cmd_area.update()

def run_kubectl(args, cmd_area=None, kubeconfig=None):
    """
    执行 kubectl 命令，确保第一次调用就生效
    :param args: kubectl 参数列表
    :param cmd_area: 可选回调，将命令插入 UI 或日志
    :param kubeconfig: 可选 kubeconfig 路径
    :return: stdout 字符串
    """
    kubectl_path = find_kubectl()
    cmd = [kubectl_path] + args

    # 复制环境变量
    env = os.environ.copy()

    # 显示指定 PATH，保证 kubectl 可执行
    env["PATH"] = "/usr/local/bin:/usr/bin:" + env.get("PATH", "")

    # 如果提供 kubeconfig，显示指定
    if kubeconfig:
        env["KUBECONFIG"] = kubeconfig

    # 如果有 UI 日志插入
    if cmd_area:
        command_insert(cmd_area, " ".join(cmd))

    # 执行命令
    res = subprocess.run(cmd, capture_output=True, text=True, env=env)

    if res.returncode != 0:
        raise RuntimeError(res.stderr.strip())

    return res.stdout.strip()


def list_contexts(force=False, cmd_area=None):
    if not force:
        v=cache_get("contexts")
        if v: return v
    out=run_kubectl(["config","get-contexts","--no-headers","-o","name"],cmd_area)
    ctx=[i.strip() for i in out.splitlines() if i.strip()]
    cache_set("contexts",ctx)
    return ctx

def list_namespaces(ctx,force=False, cmd_area=None):
    k=f"ns::{ctx}"
    if not force:
        v=cache_get(k)
        if v: return v
    out=run_kubectl(["--context",ctx,"get","ns","-o","json"],cmd_area)
    ns=[i["metadata"]["name"] for i in json.loads(out).get("items",[])]
    cache_set(k,ns)
    return ns

def list_pods(ctx,ns,force=False,cmd_area=None):
    k=f"pods::{ctx}::{ns}"
    if not force:
        v=cache_get(k)
        if v: return v
    out=run_kubectl(["--context",ctx,"-n",ns,"get","pods","-o","json"],cmd_area)
    pods=[i["metadata"]["name"] for i in json.loads(out).get("items",[])]
    cache_set(k,pods)
    return pods

def get_containers(ctx,ns,pod,cmd_area=None):
    out=run_kubectl(["--context",ctx,"-n",ns,"get","pod",pod,"-o","json"],cmd_area)
    return [c["name"] for c in json.loads(out)["spec"]["containers"]]

def pod_logs(ctx,ns,pod,container=None,tail=200,cmd_area=None):
    args=["--context",ctx,"-n",ns,"logs",pod,f"--tail={tail}"]
    if container: args+=["-c",container]
    return run_kubectl(args,cmd_area)

def delete_pod(ctx,ns,pod,cmd_area=None):
    run_kubectl(["--context",ctx,"-n",ns,"delete","pod",pod],cmd_area)
    d=load_cache()
    k=f"pods::{ctx}::{ns}"
    if k in d: del d[k]; save_cache(d)

def describe_pod(ctx,ns,pod,cmd_area=None):
    out=run_kubectl(["--context",ctx,"-n",ns,"get","pod",pod,"-o","json"],cmd_area)
    return json.loads(out)

def match_filter_option(opt,query):
    qlist=query.lower().split()
    words=opt.replace("-", " ").split()
    initials=[w[0] for w in words]
    return all(any(q in w.lower() or q==i for w,i in zip(words,initials)) for q in qlist)

class K8sSwitcher(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("K8s Switcher")
        self.update_idletasks()

        max_width, max_height = self.maxsize()
        self.geometry(f"{max_width}x{max_height}")
        self.contexts,self.namespaces,self.pods=[],[],[]
        self.current_ctx,self.current_ns,self.current_pod=None,None,None
        self.overlay=None
        self.log_search_indices=[]
        self.current_search_idx=0
        self.create_widgets()
        self.load_contexts()

    def disable_all(self):
        self.update()

    def enable_all(self):
        if self.overlay: self.overlay.destroy(); self.overlay=None
        self.update()

    def create_widgets(self):
        self.frame_ctx=ttk.LabelFrame(self,text="1)Select Clusters")
        self.frame_ctx.pack(fill=tk.BOTH,padx=6,pady=6)
        filter_frame=ttk.Frame(self.frame_ctx)
        filter_frame.pack(fill=tk.X)
        self.ctx_filter=tk.Entry(filter_frame)
        self.ctx_filter.pack(side=tk.LEFT,fill=tk.X,expand=True,padx=2)
        self.ctx_filter.bind("<KeyRelease>",lambda e:self.filter_ctx())
        self.ctx_filter.bind("<Return>",lambda e:self.ctx_enter())
        ttk.Button(filter_frame,text="Fresh",command=lambda:self.load_contexts(True)).pack(side=tk.RIGHT,padx=2)
        self.ctx_list=tk.Listbox(self.frame_ctx,height=6,exportselection=False)
        self.ctx_list.pack(fill=tk.BOTH,expand=True)
        self.ctx_list.bind("<Return>",lambda e:self.ctx_confirm())
        self.ctx_list.bind("<Double-Button-1>",lambda e:self.ctx_confirm())

        self.frame_ns=ttk.LabelFrame(self,text="2)Select Namespace")
        self.frame_ns.pack(fill=tk.BOTH,padx=6,pady=6)
        filter_frame_ns=ttk.Frame(self.frame_ns)
        filter_frame_ns.pack(fill=tk.X)
        self.ns_filter=tk.Entry(filter_frame_ns)
        self.ns_filter.pack(side=tk.LEFT,fill=tk.X,expand=True,padx=2)
        self.ns_filter.bind("<KeyRelease>",lambda e:self.filter_ns())
        self.ns_filter.bind("<Return>",lambda e:self.ns_enter())
        ttk.Button(filter_frame_ns,text="Fresh",command=lambda:self.load_ns(True)).pack(side=tk.RIGHT,padx=2)
        self.ns_list=tk.Listbox(self.frame_ns,height=6,exportselection=False)
        self.ns_list.pack(fill=tk.BOTH,expand=True)
        self.ns_list.bind("<Return>",lambda e:self.ns_confirm())
        self.ns_list.bind("<Double-Button-1>",lambda e:self.ns_confirm())

        self.frame_pod=ttk.LabelFrame(self,text="3)Select Pod")
        self.frame_pod.pack(fill=tk.BOTH,padx=6,pady=6)
        filter_frame_pod=ttk.Frame(self.frame_pod)
        filter_frame_pod.pack(fill=tk.X)
        self.pod_filter=tk.Entry(filter_frame_pod)
        self.pod_filter.pack(side=tk.LEFT,fill=tk.X,expand=True,padx=2)
        self.pod_filter.bind("<KeyRelease>",lambda e:self.filter_pod())
        self.pod_filter.bind("<Return>",lambda e:self.pod_enter())
        ttk.Button(filter_frame_pod,text="Fresh",command=lambda:self.load_pods(True)).pack(side=tk.RIGHT,padx=2)
        self.pod_list=tk.Listbox(self.frame_pod,height=8,exportselection=False)
        self.pod_list.pack(fill=tk.BOTH,expand=True)
        self.pod_list.bind("<Return>",lambda e:self.pod_confirm())
        self.pod_list.bind("<Double-Button-1>",lambda e:self.pod_confirm())

        self.frame_action=ttk.LabelFrame(self,text="4)Pod Operations")
        self.frame_action.pack(fill=tk.BOTH,padx=6,pady=6)
        self.lbl_status=ttk.Label(self.frame_action,text="No Pod selected")
        self.lbl_status.pack(anchor="w",padx=4,pady=4)
        btns=ttk.Frame(self.frame_action)
        btns.pack(fill=tk.X,padx=4,pady=4)
        ttk.Button(btns,text="Pod Log",command=self.view_logs).pack(side=tk.LEFT,padx=4)
        ttk.Button(btns,text="Delete Pod",command=self.del_pod).pack(side=tk.LEFT,padx=4)
        ttk.Button(btns,text="Enter Pod",command=self.enter_pod).pack(side=tk.LEFT,padx=4)
        ttk.Button(btns,text="Port-Forward",command=self.port_forward).pack(side=tk.LEFT,padx=4)
        ttk.Button(btns,text="Upload",command=self.upload_file).pack(side=tk.LEFT,padx=4)
        ttk.Button(btns,text="Download",command=self.download_file).pack(side=tk.LEFT,padx=4)
        ttk.Button(btns,text="Describe Pod",command=self.describe_pod).pack(side=tk.LEFT,padx=4)
        ttk.Button(btns,text="Exit",command=self.quit).pack(side=tk.RIGHT,padx=4)

        self.frame_cmd=ttk.LabelFrame(self,text="Command")
        self.frame_cmd.pack(fill=tk.BOTH,expand=True,padx=6,pady=6)
        self.cmd_text=scrolledtext.ScrolledText(self.frame_cmd,height=10,bg="black",fg="white")
        self.cmd_text.pack(fill=tk.BOTH,expand=True)

    # 筛选和确认函数省略，与之前相同
    def filter_ctx(self):
        q=self.ctx_filter.get()
        for idx,opt in enumerate(self.contexts):
            if match_filter_option(opt,q):
                self.ctx_list.selection_clear(0,tk.END)
                self.ctx_list.selection_set(idx)
                self.ctx_list.see(idx)
                break

    def filter_ns(self):
        q=self.ns_filter.get()
        for idx,opt in enumerate(self.namespaces):
            if match_filter_option(opt,q):
                self.ns_list.selection_clear(0,tk.END)
                self.ns_list.selection_set(idx)
                self.ns_list.see(idx)
                break

    def filter_pod(self):
        q=self.pod_filter.get()
        for idx,opt in enumerate(self.pods):
            if match_filter_option(opt,q):
                self.pod_list.selection_clear(0,tk.END)
                self.pod_list.selection_set(idx)
                self.pod_list.see(idx)
                break

    def ctx_enter(self): sel=self.ctx_list.curselection(); self.ctx_confirm() if sel else None
    def ns_enter(self): sel=self.ns_list.curselection(); self.ns_confirm() if sel else None
    def pod_enter(self): sel=self.pod_list.curselection(); self.pod_confirm() if sel else None

    def load_contexts(self,force=False):
        def _load():
            self.disable_all()
            try:
                self.contexts=list_contexts(force,self.cmd_text)
                self.ctx_list.delete(0,tk.END)
                for c in self.contexts: self.ctx_list.insert(tk.END,c)
                self.ctx_filter.focus_set()
            finally: self.enable_all()
        threading.Thread(target=_load,daemon=True).start()

    def load_ns(self,force=False):
        if not self.current_ctx: return
        def _load():
            self.disable_all()
            try:
                self.namespaces=list_namespaces(self.current_ctx,force,self.cmd_text)
                self.ns_list.delete(0,tk.END)
                for n in self.namespaces: self.ns_list.insert(tk.END,n)
                self.ns_filter.focus_set()
            finally: self.enable_all()
        threading.Thread(target=_load,daemon=True).start()

    def load_pods(self,force=False):
        if not self.current_ctx or not self.current_ns: return
        def _load():
            self.disable_all()
            try:
                self.pods=list_pods(self.current_ctx,self.current_ns,force,self.cmd_text)
                self.pod_list.delete(0,tk.END)
                for p in self.pods: self.pod_list.insert(tk.END,p)
                self.pod_filter.focus_set()
            finally: self.enable_all()
        threading.Thread(target=_load,daemon=True).start()

    def ctx_confirm(self):
        sel=self.ctx_list.curselection()
        if not sel: return
        self.current_ctx=self.contexts[sel[0]]
        run_kubectl(["config","use-context",self.current_ctx],self.cmd_text)
        self.lbl_status.config(text=f"selected context: {self.current_ctx}")
        self.load_ns()

    def ns_confirm(self):
        sel=self.ns_list.curselection()
        if not sel: return
        self.current_ns=self.namespaces[sel[0]]
        run_kubectl(["config","set-context","--current","--namespace",self.current_ns],self.cmd_text)
        self.lbl_status.config(text=f"selected {self.current_ctx}/{self.current_ns}")
        self.load_pods()

    def pod_confirm(self):
        sel=self.pod_list.curselection()
        if not sel: return
        self.current_pod=self.pods[sel[0]]
        self.lbl_status.config(text=f"selected {self.current_ctx}/{self.current_ns}/{self.current_pod}")

    def view_logs(self):
        if not self.current_pod: return
        def _logs():
            self.disable_all()
            container=None
            try:
                containers=get_containers(self.current_ctx,self.current_ns,self.current_pod)
                if len(containers)>1:
                    container=simpledialog.askstring("select container","this pod has multiple containers，please input the container name:",parent=self)
                    if container not in containers: messagebox.showerror("error","terminal not found"); return
                logs=pod_logs(self.current_ctx,self.current_ns,self.current_pod,container,tail=500,cmd_area=self.cmd_text)
                win=tk.Toplevel(self)
                win.title(f"Logs {self.current_pod}")
                txt=scrolledtext.ScrolledText(win,wrap="none")
                txt.insert("1.0",logs)
                txt.pack(fill=tk.BOTH,expand=True)
                search_frame=ttk.Frame(win)
                search_frame.pack(fill=tk.X)
                search_entry=tk.Entry(search_frame)
                search_entry.pack(side=tk.LEFT,fill=tk.X,expand=True)
                self.log_search_indices=[]
                self.current_search_idx=0
                def search_next():
                    if not self.log_search_indices:
                        s=search_entry.get()
                        txt.tag_remove('highlight','1.0',tk.END)
                        self.log_search_indices=[]
                        self.current_search_idx=0
                        if not s: return
                        idx='1.0'
                        while True:
                            idx=txt.search(s,idx,stopindex=tk.END)
                            if not idx: break
                            lastidx=f"{idx}+{len(s)}c"
                            txt.tag_add('highlight',idx,lastidx)
                            self.log_search_indices.append(idx)
                            idx=lastidx
                        txt.tag_config('highlight',background='yellow')
                    if self.log_search_indices:
                        idx=self.log_search_indices[self.current_search_idx]
                        txt.see(idx)
                        txt.mark_set("insert",idx)
                        self.current_search_idx=(self.current_search_idx+1)%len(self.log_search_indices)
                ttk.Button(search_frame,text="下一个匹配",command=search_next).pack(side=tk.RIGHT)
            finally: self.enable_all()
        threading.Thread(target=_logs,daemon=True).start()

    def del_pod(self):
        if not self.current_pod: return
        if not messagebox.askyesno("confirm",f"delete pod {self.current_pod}?"): return
        def _del():
            self.disable_all()
            try: delete_pod(self.current_ctx,self.current_ns,self.current_pod,self.cmd_text); self.load_pods()
            finally: self.enable_all()
        threading.Thread(target=_del,daemon=True).start()

    def enter_pod(self):
        if not self.current_pod: return
        term=shutil.which("xterm") or shutil.which("gnome-terminal")
        if not term: messagebox.showerror("error","terminal not found"); return
        def _exec():
            self.disable_all()
            try:
                for shell in ["bash","sh"]:
                    try:
                        cmd=[term,"-e",f"kubectl --context {self.current_ctx} -n {self.current_ns} exec -it {self.current_pod} -- {shell}"]
                        command_insert(self.cmd_text," ".join(cmd))
                        subprocess.Popen(cmd)
                        break
                    except: continue
            finally: self.enable_all()
        threading.Thread(target=_exec,daemon=True).start()

    def port_forward(self):
        if not self.current_pod: return
        port=simpledialog.askstring("Port Forward","please input local port:remote port",parent=self)
        if not port or ":" not in port: return
        term=shutil.which("xterm") or shutil.which("gnome-terminal")
        if not term: messagebox.showerror("error","terminal not found"); return
        def _pf():
            self.disable_all()
            try:
                cmd=[term,"-e",f"kubectl --context {self.current_ctx} -n {self.current_ns} port-forward {self.current_pod} {port}"]
                command_insert(self.cmd_text," ".join(cmd))
                subprocess.Popen(cmd)
            finally: self.enable_all()
        threading.Thread(target=_pf,daemon=True).start()

    def upload_file(self):
        if not self.current_pod: 
            messagebox.showwarning("warning","Please select a pod first")
            return
        file_path = filedialog.askopenfilename(title="Select a file to upload")
        if not file_path: return
        dest_path = f"/tmp/{os.path.basename(file_path)}"
        
        def _upload():
            self.disable_all()
            try:
                run_kubectl(["--context", self.current_ctx, "-n", self.current_ns,
                             "cp", file_path, f"{self.current_pod}:{dest_path}"], self.cmd_text)
                messagebox.showinfo("Done", f"Uploaded to {self.current_pod}:{dest_path}")
            except Exception as e:
                messagebox.showerror("Error", str(e))
            finally:
                self.enable_all()
        threading.Thread(target=_upload, daemon=True).start()


    def download_file(self):
        if not self.current_pod:
            messagebox.showwarning("warning","Please select a pod first")
            return
        file_in_pod = simpledialog.askstring("Download", "Enter the file path in pod:", parent=self)
        if not file_in_pod: return
        local_dir = str(Path.home())
        prefix = "download" + datetime.datetime.now().strftime("%Y%m%d")
        local_file = os.path.join(local_dir, f"{prefix}_{os.path.basename(file_in_pod)}")

        def _download():
            self.disable_all()
            try:
                run_kubectl(["--context", self.current_ctx, "-n", self.current_ns,
                             "cp", f"{self.current_pod}:{file_in_pod}", local_file], self.cmd_text)
                messagebox.showinfo("Done", f"Downloaded to {local_file}")
            except Exception as e:
                messagebox.showerror("Error", str(e))
            finally:
                self.enable_all()
        threading.Thread(target=_download, daemon=True).start()
    def describe_pod(self):
        if not self.current_pod:
            messagebox.showwarning("warning","Please select a pod first")
            return
        
        def _describe():
            self.disable_all()
            try:
                pod_info = describe_pod(self.current_ctx, self.current_ns, self.current_pod, self.cmd_text)

                win = tk.Toplevel(self)
                win.title(f"Pod Details - {self.current_pod}")
                win.geometry("800x600")

                txt = scrolledtext.ScrolledText(win, wrap=tk.WORD)
                txt.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

                details = self._format_pod_details(pod_info)
                txt.insert("1.0", details)
                txt.config(state=tk.DISABLED)
                
            except Exception as e:
                messagebox.showerror("Error", f"Failed to get pod details: {str(e)}")
            finally:
                self.enable_all()
        
        threading.Thread(target=_describe, daemon=True).start()
    def _format_pod_details(self, pod_info):
        """格式化pod详细信息"""
        details = []
        
        # 基本信息
        metadata = pod_info.get("metadata", {})
        details.append("=== POD基本信息 ===\n")
        details.append(f"名称: {metadata.get('name', 'N/A')}\n")
        details.append(f"命名空间: {metadata.get('namespace', 'N/A')}\n")
        details.append(f"创建时间: {metadata.get('creationTimestamp', 'N/A')}\n")
        
        # Pod状态
        status = pod_info.get("status", {})
        details.append(f"状态: {status.get('phase', 'N/A')}\n")
        details.append(f"节点: {status.get('hostIP', 'N/A')}\n")
        details.append(f"Pod IP: {status.get('podIP', 'N/A')}\n")
        
        details.append("\n=== 容器信息 ===\n")
        
        # 容器信息
        spec = pod_info.get("spec", {})
        containers = spec.get("containers", [])
        
        for i, container in enumerate(containers):
            details.append(f"\n--- 容器 {i+1}: {container.get('name', 'N/A')} ---\n")
            
            # 镜像信息
            image = container.get('image', 'N/A')
            details.append(f"  镜像: {image}\n")
            
            # 解析镜像标签
            if ':' in image:
                image_parts = image.split(':')
                if len(image_parts) > 1:
                    details.append(f"  镜像标签: {image_parts[-1]}\n")
            
            # 端口信息
            ports = container.get('ports', [])
            if ports:
                details.append("  端口:\n")
                for port in ports:
                    container_port = port.get('containerPort', 'N/A')
                    protocol = port.get('protocol', 'TCP')
                    name = port.get('name', '')
                    details.append(f"    - {container_port}/{protocol} {name}\n")
            else:
                details.append("  端口: 无暴露端口\n")
            
            # 环境变量
            env_vars = container.get('env', [])
            if env_vars:
                details.append("  环境变量:\n")
                for env in env_vars[:10]:  # 只显示前10个
                    name = env.get('name', 'N/A')
                    value = env.get('value', '')
                    if not value:
                        value_from = env.get('valueFrom', {})
                        if value_from:
                            value = "[来自配置]"
                    details.append(f"    - {name}={value}\n")
                if len(env_vars) > 10:
                    details.append(f"    ... 还有 {len(env_vars)-10} 个环境变量\n")
            
            # 资源限制
            resources = container.get('resources', {})
            if resources:
                details.append("  资源限制:\n")
                limits = resources.get('limits', {})
                requests = resources.get('requests', {})
                
                if limits:
                    details.append("    限制:\n")
                    for key, value in limits.items():
                        details.append(f"      {key}: {value}\n")
                
                if requests:
                    details.append("    请求:\n")
                    for key, value in requests.items():
                        details.append(f"      {key}: {value}\n")
        
        # 卷配置
        volumes = spec.get('volumes', [])
        if volumes:
            details.append("\n=== 存储卷配置 ===\n")
            for volume in volumes:
                name = volume.get('name', 'N/A')
                details.append(f"\n卷: {name}\n")
                
                # 检查不同类型的卷
                if 'persistentVolumeClaim' in volume:
                    pvc = volume['persistentVolumeClaim']
                    details.append(f"  类型: PersistentVolumeClaim\n")
                    details.append(f"  PVC名称: {pvc.get('claimName', 'N/A')}\n")
                elif 'configMap' in volume:
                    cm = volume['configMap']
                    details.append(f"  类型: ConfigMap\n")
                    details.append(f"  ConfigMap名称: {cm.get('name', 'N/A')}\n")
                elif 'secret' in volume:
                    secret = volume['secret']
                    details.append(f"  类型: Secret\n")
                    details.append(f"  Secret名称: {secret.get('secretName', 'N/A')}\n")
                elif 'emptyDir' in volume:
                    details.append(f"  类型: EmptyDir\n")
                elif 'hostPath' in volume:
                    hp = volume['hostPath']
                    details.append(f"  类型: HostPath\n")
                    details.append(f"  主机路径: {hp.get('path', 'N/A')}\n")
        
        labels = metadata.get('labels', {})
        if labels:
            details.append("\n=== 标签 ===\n")
            for key, value in labels.items():
                details.append(f"{key}: {value}\n")
        
        annotations = metadata.get('annotations', {})
        if annotations:
            details.append("\n=== 注解 ===\n")
            for key, value in list(annotations.items())[:5]:  # 只显示前5个注解
                details.append(f"{key}: {value}\n")
            if len(annotations) > 5:
                details.append(f"... 还有 {len(annotations)-5} 个注解\n")
        
        return "".join(details)

if __name__=="__main__":
    app=K8sSwitcher()
    app.mainloop()

