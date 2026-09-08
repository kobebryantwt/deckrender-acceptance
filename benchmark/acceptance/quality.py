"""Current quality evaluator binding; historical v1 implementation is retained."""
from .versioned import load
_module=load('render-quality','quality','4')
globals().update({k:v for k,v in vars(_module).items() if not k.startswith('_')})
