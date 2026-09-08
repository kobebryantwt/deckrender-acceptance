import json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[3]))
from acceptance.evaluator_v4_entry import evaluate
print(json.dumps(evaluate(json.loads(Path(sys.argv[1]).read_text())),ensure_ascii=False))
