from fruitbox_pygame.vs import FruitBoxVs
from .onnx_agent import OnnxAgent
from ._resource import resource_path

MODEL_PATH = resource_path("fruitbox_policy.onnx")


class OnnxVs(FruitBoxVs):
    def _create_model(self):
        return OnnxAgent(MODEL_PATH)
