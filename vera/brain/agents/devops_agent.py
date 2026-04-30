"""DevOps Agent -- Docker, Kubernetes, CI/CD, cloud deployment, monitoring.

No consumer AI has this: full infrastructure management from voice.
"""
from __future__ import annotations
import logging, subprocess
from typing import Any
from vera.brain.agents.base import BaseAgent, Tool
from vera.providers.models import ModelTier
logger = logging.getLogger(__name__)

class DockerTool(Tool):
    """Manage Docker containers/images."""
    def __init__(self): super().__init__(name="docker_manage",description="Docker: ps/images/run/stop/rm/build/logs/pull",parameters={"action":{"type":"str","description":"ps|images|run|stop|rm|build|logs|pull"},"container":{"type":"str","description":"Container name/ID"},"image":{"type":"str","description":"Image name"},"command":{"type":"str","description":"Run command"}})
    async def execute(self, **kw: Any) -> dict[str, Any]:
        a=kw.get("action","ps")
        try:
            if a=="ps": r=subprocess.run(["docker","ps","--format","{{.ID}}\t{{.Names}}\t{{.Status}}\t{{.Image}}"],capture_output=True,text=True); return {"status":"success","containers":[dict(zip(["id","name","status","image"],l.split("\t"))) for l in r.stdout.strip().split("\n") if l]}
            elif a=="images": r=subprocess.run(["docker","images","--format","{{.Repository}}:{{.Tag}}\t{{.Size}}"],capture_output=True,text=True); return {"status":"success","images":[dict(zip(["name","size"],l.split("\t"))) for l in r.stdout.strip().split("\n") if l]}
            elif a=="run": r=subprocess.run(["docker","run","-d","--name",kw.get("container","vera_c"),kw.get("image","")],capture_output=True,text=True); return {"status":"success","id":r.stdout.strip()[:12]}
            elif a=="stop": subprocess.run(["docker","stop",kw["container"]],capture_output=True); return {"status":"success","stopped":kw["container"]}
            elif a=="rm": subprocess.run(["docker","rm","-f",kw["container"]],capture_output=True); return {"status":"success","removed":kw["container"]}
            elif a=="logs": r=subprocess.run(["docker","logs","--tail","50",kw["container"]],capture_output=True,text=True); return {"status":"success","logs":r.stdout[-3000:]}
            elif a=="pull": subprocess.run(["docker","pull",kw["image"]],capture_output=True); return {"status":"success","pulled":kw["image"]}
            elif a=="build": subprocess.run(["docker","build","-t",kw.get("image","app"),"."],capture_output=True); return {"status":"success","built":kw.get("image","app")}
        except Exception as e: return {"status":"error","message":str(e)}

class KubernetesTool(Tool):
    """Kubernetes operations."""
    def __init__(self): super().__init__(name="kubectl",description="K8s: get/describe/apply/delete/logs/scale",parameters={"action":{"type":"str","description":"get|describe|apply|delete|logs|scale"},"resource":{"type":"str","description":"pods|services|deployments"},"name":{"type":"str","description":"Resource name"},"namespace":{"type":"str","description":"Namespace"},"replicas":{"type":"int","description":"Scale replicas"},"file":{"type":"str","description":"YAML for apply"}})
    async def execute(self, **kw: Any) -> dict[str, Any]:
        a,res,name,ns=kw.get("action","get"),kw.get("resource","pods"),kw.get("name",""),kw.get("namespace","default")
        try:
            if a=="scale": cmd=["kubectl","scale",f"deployment/{name}",f"--replicas={kw.get('replicas',1)}","-n",ns]
            elif a=="apply": cmd=["kubectl","apply","-f",kw.get("file",""),"-n",ns]
            elif a=="logs": cmd=["kubectl","logs","--tail=50",name,"-n",ns]
            else: cmd=["kubectl",a,res]+([ name] if name else [])+["-n",ns]
            r=subprocess.run(cmd,capture_output=True,text=True)
            return {"status":"success","output":r.stdout[:3000] or r.stderr[:1000]}
        except Exception as e: return {"status":"error","message":str(e)}

class SystemMonitorTool(Tool):
    """Monitor system resources."""
    def __init__(self): super().__init__(name="system_monitor",description="Monitor CPU/memory/disk/network/processes",parameters={"metric":{"type":"str","description":"cpu|memory|disk|network|processes|all"}})
    async def execute(self, **kw: Any) -> dict[str, Any]:
        try:
            import psutil; m=kw.get("metric","all"); result={}
            if m in ("cpu","all"): result["cpu"]={"percent":psutil.cpu_percent(interval=1),"cores":psutil.cpu_count()}
            if m in ("memory","all"): mem=psutil.virtual_memory(); result["memory"]={"total_gb":round(mem.total/1e9,2),"used_gb":round(mem.used/1e9,2),"percent":mem.percent}
            if m in ("disk","all"): disk=psutil.disk_usage("/"); result["disk"]={"total_gb":round(disk.total/1e9,2),"used_gb":round(disk.used/1e9,2),"percent":disk.percent}
            if m in ("network","all"): net=psutil.net_io_counters(); result["network"]={"sent_mb":round(net.bytes_sent/1e6,2),"recv_mb":round(net.bytes_recv/1e6,2)}
            if m in ("processes","all"): result["top_processes"]=[{"pid":p.info["pid"],"name":p.info["name"]} for p in sorted(psutil.process_iter(["pid","name","cpu_percent"]),key=lambda p:p.info.get("cpu_percent",0) or 0,reverse=True)[:10]]
            return {"status":"success",**result}
        except ImportError: return {"status":"error","message":"pip install psutil"}
        except Exception as e: return {"status":"error","message":str(e)}

class SSHTool(Tool):
    """Execute commands on remote servers."""
    def __init__(self): super().__init__(name="ssh_execute",description="Run command on remote server via SSH",parameters={"host":{"type":"str","description":"SSH host"},"command":{"type":"str","description":"Command"},"user":{"type":"str","description":"SSH user"},"port":{"type":"int","description":"SSH port"}})
    async def execute(self, **kw: Any) -> dict[str, Any]:
        try:
            import paramiko; c=paramiko.SSHClient(); c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            c.connect(kw["host"],port=kw.get("port",22),username=kw.get("user","root"))
            _,stdout,stderr=c.exec_command(kw["command"]); out=stdout.read().decode()[:3000]; err=stderr.read().decode()[:1000]; c.close()
            return {"status":"success","stdout":out,"stderr":err}
        except ImportError: return {"status":"error","message":"pip install paramiko"}
        except Exception as e: return {"status":"error","message":str(e)}

class DockerComposeTool(Tool):
    """Docker Compose operations."""
    def __init__(self): super().__init__(name="docker_compose",description="Docker Compose: up/down/ps/logs/build/restart",parameters={"action":{"type":"str","description":"up|down|ps|logs|build|restart"},"file":{"type":"str","description":"Compose file path"},"service":{"type":"str","description":"Service name"}})
    async def execute(self, **kw: Any) -> dict[str, Any]:
        a,f=kw.get("action","ps"),kw.get("file","docker-compose.yml")
        cmd=["docker","compose","-f",f,a]; svc=kw.get("service","")
        if a=="up": cmd=["docker","compose","-f",f,"up","-d"]
        if a=="logs": cmd=["docker","compose","-f",f,"logs","--tail=50"]+([ svc] if svc else [])
        try:
            r=subprocess.run(cmd,capture_output=True,text=True)
            return {"status":"success","output":(r.stdout or r.stderr)[:3000]}
        except Exception as e: return {"status":"error","message":str(e)}

class CICDTool(Tool):
    """CI/CD pipeline management."""
    def __init__(self): super().__init__(name="cicd_pipeline",description="GitHub Actions: list/trigger/status",parameters={"action":{"type":"str","description":"list|trigger|status"},"repo":{"type":"str","description":"owner/repo"},"workflow":{"type":"str","description":"Workflow name/ID"}})
    async def execute(self, **kw: Any) -> dict[str, Any]:
        try:
            import httpx, os; token=os.getenv("GITHUB_TOKEN",""); repo=kw.get("repo","")
            async with httpx.AsyncClient(timeout=10) as c:
                if kw.get("action")=="list":
                    r=await c.get(f"https://api.github.com/repos/{repo}/actions/runs",headers={"Authorization":f"token {token}","Accept":"application/vnd.github.v3+json"})
                    runs=r.json().get("workflow_runs",[])[:5]
                    return {"status":"success","runs":[{"name":r["name"],"status":r["status"],"conclusion":r.get("conclusion")} for r in runs]}
                elif kw.get("action")=="trigger":
                    r=await c.post(f"https://api.github.com/repos/{repo}/actions/workflows/{kw.get('workflow','')}/dispatches",headers={"Authorization":f"token {token}"},json={"ref":"main"})
                    return {"status":"success" if r.status_code==204 else "error"}
            return {"status":"success","action":kw.get("action")}
        except Exception as e: return {"status":"error","message":str(e)}

class NginxConfigTool(Tool):
    """Generate/test Nginx configuration."""
    def __init__(self): super().__init__(name="nginx_config",description="Generate/test/reload Nginx config",parameters={"action":{"type":"str","description":"generate|test|reload"},"domain":{"type":"str","description":"Domain"},"upstream":{"type":"str","description":"Upstream host:port"}})
    async def execute(self, **kw: Any) -> dict[str, Any]:
        a=kw.get("action","generate")
        if a=="generate":
            d,u=kw.get("domain","example.com"),kw.get("upstream","localhost:8000")
            return {"status":"success","config":f"server {{\n    listen 80;\n    server_name {d};\n    location / {{\n        proxy_pass http://{u};\n        proxy_set_header Host $host;\n    }}\n}}"}
        elif a in ("test","reload"):
            r=subprocess.run(["nginx","-t" if a=="test" else "-s","reload" if a=="reload" else ""],capture_output=True,text=True)
            return {"status":"success","output":r.stderr or r.stdout}
        return {"status":"error","message":f"Unknown: {a}"}

class CloudDeployTool(Tool):
    """Deploy to cloud providers."""
    def __init__(self): super().__init__(name="cloud_deploy",description="Deploy to AWS/GCP/Azure",parameters={"provider":{"type":"str","description":"aws|gcp|azure"},"service":{"type":"str","description":"Service name"},"action":{"type":"str","description":"deploy|status|logs"}})
    async def execute(self, **kw: Any) -> dict[str, Any]:
        p,svc,a=kw.get("provider","aws"),kw.get("service",""),kw.get("action","status")
        try:
            if p=="aws": cmd=["aws","ecs","describe-services" if a=="status" else "update-service","--cluster","default","--services",svc]
            elif p=="gcp": cmd=["gcloud","run","services",a,svc]
            else: cmd=["az","webapp",a,"--name",svc]
            r=subprocess.run(cmd,capture_output=True,text=True)
            return {"status":"success","output":(r.stdout or r.stderr)[:3000]}
        except Exception as e: return {"status":"error","message":str(e)}

class DevOpsAgent(BaseAgent):
    """Docker, Kubernetes, CI/CD, cloud, monitoring, SSH, Nginx."""
    name = "devops"
    description = "Docker, Kubernetes, CI/CD, cloud deploy, system monitoring, SSH, Nginx, Docker Compose"
    tier = ModelTier.SPECIALIST
    system_prompt = "You are eVera's DevOps Agent. Manage Docker, Kubernetes, CI/CD, cloud deployments, system monitoring, SSH, Nginx, and Docker Compose."
    offline_responses = {"docker":"\U0001f433 Docker!","deploy":"\U0001f680 Deploying!","kubernetes":"\u2638 K8s!","monitor":"\U0001f4ca Monitoring!","server":"\U0001f5a5 Server ops!"}
    def _setup_tools(self): self._tools = [DockerTool(),KubernetesTool(),SystemMonitorTool(),SSHTool(),DockerComposeTool(),CICDTool(),NginxConfigTool(),CloudDeployTool()]
