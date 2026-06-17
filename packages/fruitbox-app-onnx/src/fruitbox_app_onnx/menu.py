from fruitbox_pygame.menu import FruitBoxMenu

from .ai_watch import OnnxAiWatch
from .vs import OnnxVs


class OnnxMenu(FruitBoxMenu):
    vs_class = OnnxVs
    watch_class = OnnxAiWatch
    model_opponent = "onnx"
