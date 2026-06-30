
import sys
import json
import argparse
from pathlib import Path

CUA_PATH = Path("C:/Users/ASUS/cua_skill")
if CUA_PATH.exists():
    sys.path.insert(0, str(CUA_PATH))

def run_replay_agent(instruction, task_graph_path=None, config_path=None):
    try:
        from agent import CUAKnowledgeGraphAgent
        
        if config_path is None:
            config_path = "C:/Users/ASUS/cua_skill/agent/config.json"
        
        agent = CUAKnowledgeGraphAgent(config=config_path)
        
        example = None
        if task_graph_path and Path(task_graph_path).exists():
            with open(task_graph_path, 'r', encoding='utf-8') as f:
                example = json.load(f)
        
        print(f"[Replay Agent] Executing: {instruction}")
        agent.proceed(instruction=instruction, example=example)
        print("[Replay Agent] Task completed successfully")
        
    except Exception as e:
        print(f"[Error] Replay Agent failed: {e}")
        return False
    
    return True

def run_rag_agent(instruction, config_path=None):
    try:
        from agent import CUARAGAgent
        
        if config_path is None:
            config_path = "C:/Users/ASUS/cua_skill/agent/config_rag.json"
        
        agent = CUARAGAgent(config=config_path)
        
        print(f"[RAG Agent] Executing: {instruction}")
        agent.proceed(instruction=instruction)
        print("[RAG Agent] Task completed successfully")
        
    except Exception as e:
        print(f"[Error] RAG Agent failed: {e}")
        return False
    
    return True

def main():
    parser = argparse.ArgumentParser(
        description="Microsoft CUA Skill - Quick Launcher",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python run_cua_agent.py --mode replay --instruction "Open Notepad and type Hello"
  
  python run_cua_agent.py --mode rag --instruction "Search for weather on Bing"
  
  python run_cua_agent.py --mode rag --config my_config.json --instruction "Open Chrome"

Supported Applications:
  - Windows Start/Search/Run
  - Bing Search, Google Chrome, Microsoft Edge
  - Microsoft Excel, Word, PowerPoint
  - Notepad, Paint, Calculator, Clock
  - File Explorer, VLC, VS Code, Amazon, YouTube, Windows Settings
