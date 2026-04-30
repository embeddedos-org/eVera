"""PDF Agent -- create, merge, split, extract text, convert PDFs."""
from __future__ import annotations
import logging
from typing import Any
from vera.brain.agents.base import BaseAgent, Tool
from vera.providers.models import ModelTier
logger = logging.getLogger(__name__)

class PDFReadTool(Tool):
    def __init__(self): super().__init__(name="pdf_read",description="Extract text from PDF",parameters={"file_path":{"type":"str","description":"PDF path"},"pages":{"type":"str","description":"Page range (e.g., 1-5 or all)"}})
    async def execute(self, **kw: Any) -> dict[str, Any]:
        try:
            import PyPDF2
            with open(kw["file_path"],"rb") as f:
                reader=PyPDF2.PdfReader(f); text=""; total=len(reader.pages)
                for i,page in enumerate(reader.pages[:20]): text+=f"\n--- Page {i+1} ---\n"+page.extract_text()
            return {"status":"success","text":text[:5000],"total_pages":total}
        except ImportError: return {"status":"error","message":"pip install PyPDF2"}
        except Exception as e: return {"status":"error","message":str(e)}

class PDFMergeTool(Tool):
    def __init__(self): super().__init__(name="pdf_merge",description="Merge multiple PDFs",parameters={"files":{"type":"str","description":"Comma-separated PDF paths"},"output":{"type":"str","description":"Output path"}})
    async def execute(self, **kw: Any) -> dict[str, Any]:
        try:
            import PyPDF2; merger=PyPDF2.PdfMerger()
            for f in kw.get("files","").split(","): merger.append(f.strip())
            out=kw.get("output","merged.pdf"); merger.write(out); merger.close()
            return {"status":"success","output":out}
        except ImportError: return {"status":"error","message":"pip install PyPDF2"}
        except Exception as e: return {"status":"error","message":str(e)}

class PDFSplitTool(Tool):
    def __init__(self): super().__init__(name="pdf_split",description="Split PDF into pages",parameters={"file_path":{"type":"str","description":"PDF path"},"pages":{"type":"str","description":"Pages to extract (e.g., 1,3,5 or 1-5)"},"output":{"type":"str","description":"Output path"}})
    async def execute(self, **kw: Any) -> dict[str, Any]:
        try:
            import PyPDF2
            with open(kw["file_path"],"rb") as f: reader=PyPDF2.PdfReader(f); writer=PyPDF2.PdfWriter()
            pages_str=kw.get("pages","1")
            if "-" in pages_str: s,e=map(int,pages_str.split("-")); page_nums=range(s-1,e)
            else: page_nums=[int(p)-1 for p in pages_str.split(",")]
            for p in page_nums:
                if p<len(reader.pages): writer.add_page(reader.pages[p])
            out=kw.get("output","split.pdf")
            with open(out,"wb") as f: writer.write(f)
            return {"status":"success","output":out,"pages":len(writer.pages)}
        except ImportError: return {"status":"error","message":"pip install PyPDF2"}
        except Exception as e: return {"status":"error","message":str(e)}

class PDFCreateTool(Tool):
    def __init__(self): super().__init__(name="pdf_create",description="Create PDF from text/HTML",parameters={"content":{"type":"str","description":"Text or HTML content"},"title":{"type":"str","description":"Document title"},"output":{"type":"str","description":"Output path"}})
    async def execute(self, **kw: Any) -> dict[str, Any]:
        try:
            from reportlab.lib.pagesizes import letter; from reportlab.pdfgen import canvas
            out=kw.get("output","document.pdf"); c=canvas.Canvas(out,pagesize=letter)
            c.setTitle(kw.get("title","Document")); c.setFont("Helvetica",12)
            y=750; lines=kw.get("content","").split("\n")
            for line in lines:
                if y<50: c.showPage(); c.setFont("Helvetica",12); y=750
                c.drawString(72,y,line); y-=15
            c.save()
            return {"status":"success","output":out}
        except ImportError: return {"status":"error","message":"pip install reportlab"}
        except Exception as e: return {"status":"error","message":str(e)}

class PDFInfoTool(Tool):
    def __init__(self): super().__init__(name="pdf_info",description="Get PDF metadata",parameters={"file_path":{"type":"str","description":"PDF path"}})
    async def execute(self, **kw: Any) -> dict[str, Any]:
        try:
            import PyPDF2
            with open(kw["file_path"],"rb") as f:
                r=PyPDF2.PdfReader(f); meta=r.metadata
            return {"status":"success","pages":len(r.pages),"title":meta.title if meta else "","author":meta.author if meta else "","creator":meta.creator if meta else ""}
        except ImportError: return {"status":"error","message":"pip install PyPDF2"}
        except Exception as e: return {"status":"error","message":str(e)}

class PDFAgent(BaseAgent):
    name = "pdf"
    description = "PDF reading, merging, splitting, creation, metadata extraction"
    tier = ModelTier.SPECIALIST
    system_prompt = "You are eVera's PDF Agent. Read, merge, split, create PDFs and extract metadata."
    offline_responses = {"pdf":"\U0001f4c4 PDF ready!","merge":"\U0001f4c4 Merging!","split":"\u2702 Splitting!","read":"\U0001f4d6 Reading!"}
    def _setup_tools(self): self._tools = [PDFReadTool(),PDFMergeTool(),PDFSplitTool(),PDFCreateTool(),PDFInfoTool()]
