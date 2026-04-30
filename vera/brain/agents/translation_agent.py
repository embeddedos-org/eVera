"""Translation Agent -- multi-language translation, detection, dictionary."""
from __future__ import annotations
import logging
from typing import Any
from vera.brain.agents.base import BaseAgent, Tool
from vera.providers.models import ModelTier
logger = logging.getLogger(__name__)

class TranslateTool(Tool):
    def __init__(self): super().__init__(name="translate_text",description="Translate text between 100+ languages",parameters={"text":{"type":"str","description":"Text to translate"},"source":{"type":"str","description":"Source language (auto)"},"target":{"type":"str","description":"Target language (en,es,fr,de,ja,zh,ko,etc)"}})
    async def execute(self, **kw: Any) -> dict[str, Any]:
        try:
            from deep_translator import GoogleTranslator
            translated=GoogleTranslator(source=kw.get("source","auto"),target=kw.get("target","en")).translate(kw.get("text",""))
            return {"status":"success","original":kw.get("text",""),"translated":translated,"target":kw.get("target","en")}
        except ImportError:
            try:
                import httpx
                async with httpx.AsyncClient(timeout=10) as c:
                    r=await c.get(f"https://api.mymemory.translated.net/get?q={kw.get('text','')}&langpair={kw.get('source','en')}|{kw.get('target','es')}")
                return {"status":"success","translated":r.json()["responseData"]["translatedText"]}
            except Exception as e: return {"status":"error","message":str(e)}
        except Exception as e: return {"status":"error","message":str(e)}

class LanguageDetectTool(Tool):
    def __init__(self): super().__init__(name="detect_language",description="Detect language of text",parameters={"text":{"type":"str","description":"Text"}})
    async def execute(self, **kw: Any) -> dict[str, Any]:
        try:
            from langdetect import detect, detect_langs
            lang=detect(kw.get("text","")); probs=detect_langs(kw.get("text",""))
            return {"status":"success","language":lang,"probabilities":[{"lang":str(p).split(":")[0],"prob":float(str(p).split(":")[1])} for p in probs[:3]]}
        except ImportError: return {"status":"error","message":"pip install langdetect"}
        except Exception as e: return {"status":"error","message":str(e)}

class DictionaryTool(Tool):
    def __init__(self): super().__init__(name="dictionary_lookup",description="Look up word definitions/synonyms",parameters={"word":{"type":"str","description":"Word to look up"},"language":{"type":"str","description":"Language code"}})
    async def execute(self, **kw: Any) -> dict[str, Any]:
        try:
            import httpx
            async with httpx.AsyncClient(timeout=10) as c:
                r=await c.get(f"https://api.dictionaryapi.dev/api/v2/entries/{kw.get('language','en')}/{kw.get('word','')}")
                if r.status_code==200:
                    d=r.json()[0]; return {"status":"success","word":d["word"],"phonetic":d.get("phonetic",""),"meanings":[{"part":m["partOfSpeech"],"defs":[df["definition"] for df in m["definitions"][:3]]} for m in d.get("meanings",[])]}
            return {"status":"error","message":"Word not found"}
        except Exception as e: return {"status":"error","message":str(e)}

class TranslationAgent(BaseAgent):
    name = "translation"
    description = "Multi-language translation, language detection, dictionary lookup"
    tier = ModelTier.SPECIALIST
    system_prompt = "You are eVera's Translation Agent. Translate between 100+ languages, detect languages, look up word definitions."
    offline_responses = {"translate":"\U0001f30d Translating!","language":"\U0001f5e3 Detecting!","dictionary":"\U0001f4d6 Looking up!"}
    def _setup_tools(self): self._tools = [TranslateTool(),LanguageDetectTool(),DictionaryTool()]
