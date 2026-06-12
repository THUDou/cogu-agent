import sys
import json

def main():
    name = sys.argv[1] if len(sys.argv) > 1 else "World"
    print(json.dumps({"greeting": f"Hello, {name}!", "from": "COGU hello-world skill"}))

if __name__ == "__main__":
    main()
