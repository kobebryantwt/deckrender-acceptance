import importlib.util
from .common import REPO

def load(evaluator,module,version='1'):
    path=REPO/'benchmark/evaluators'/evaluator/version/(module+'.py')
    spec=importlib.util.spec_from_file_location(evaluator.replace('-','_')+'_'+version+'_'+module,path)
    loaded=importlib.util.module_from_spec(spec);spec.loader.exec_module(loaded)
    return loaded
