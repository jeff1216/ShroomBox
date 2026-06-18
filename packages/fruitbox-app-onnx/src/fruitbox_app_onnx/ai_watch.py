from fruitbox_pygame.ai_watch import FruitBoxAiWatch
from .onnx_agent import OnnxAgent
from ._resource import resource_path

MODEL_PATH = resource_path("fruitbox_policy.onnx")


class OnnxAiWatch(FruitBoxAiWatch):
    def _create_model(self):
        return OnnxAgent(MODEL_PATH)
