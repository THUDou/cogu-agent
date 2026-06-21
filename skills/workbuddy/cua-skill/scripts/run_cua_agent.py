#!/usr/bin/env python3
"""
Quick launcher for Microsoft CUA Skill
Supports both Replay and RAG agent modes
"""

import sys
import json
import argparse
from pathlib import Path

# Add CUA Skill to Python path
CUA_PATH = Path("C:/Users/ASUS/cua_skill")
if CUA_PATH.exists():
    sys.path.insert(0, str(CUA_PATH))

def run_replay_agent(instruction, task_graph_path=None, config_path=None):
    """Run Replay Agent with a pre-defined task graph"""
    try:
        from agent import CUAKnowledgeGraphAgent
        
        if config_path is None:
            config_path = "C:/Users/ASUS/cua_skill/agent/config.json"
        
        agent = CUAKnowledgeGraphAgent(config=config_path)
        
        # Load task graph if provided
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
    """Run RAG Agent with dynamic task planning"""
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
  # Run Replay Agent with a task graph
  python run_cua_agent.py --mode replay --instruction "Open Notepad and type Hello"
  
  # Run RAG Agent with dynamic planning
  python run_cua_agent.py --mode rag --instruction "Search for weather on Bing"
  
  # Use custom config file
  python run_cua_agent.py --mode rag --config my_config.json --instruction "Open Chrome"

Supported Applications:
  - Windows Start/Search/Run
  - Bing Search, Google Chrome, Microsoft Edge
  - Microsoft Excel, Word, PowerPoint
  - Notepad, Paint, Calculator, Clock
  - File Explorer, VLC, VS Code, Amazon, YouTube, Windows Settings
"""
    )
    
    parser.add_argument(
        "--mode",
        choices=["replay", "rag"],
        default="rag",
        help="Agent mode: replay (pre-defined tasks) or rag (dynamic planning)"
    )
    
    parser.add_argument(
        "--instruction",
        type=str,
        required=True,
        help="Natural language instruction for the agent"
    )
    
    parser.add_argument(
        "--config",
        type=str,
        help="Path to custom config file (optional)"
    )
    
    parser.add_argument(
        "--task-graph",
        type=str,
        help="Path to task graph JSON file (for replay mode)"
    )
    
    args = parser.parse_args()
    
    # Check if CUA Skill is installed
    if not CUA_PATH.exists():
        print(f"[Error] CUA Skill not found at {CUA_PATH}")
        print("Please clone the repository first:")
        print("  git clone https://github.com/microsoft/cua_skill.git C:/Users/ASUS/cua_skill")
        sys.exit(1)
    
    # Execute based on mode
    if args.mode == "replay":
        success = run_replay_agent(
            instruction=args.instruction,
            task_graph_path=args.task_graph,
            config_path=args.config
        )
    else:  # rag mode
        success = run_rag_agent(
            instruction=args.instruction,
            config_path=args.config
        )
    
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()
