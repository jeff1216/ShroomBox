from sb3_contrib import MaskablePPO

from fruitbox_pygame.ai_watch import FruitBoxAiWatch
from ._resource import resource_path

MODEL_PATH = resource_path("fruitbox_ppo_final")


class TorchAiWatch(FruitBoxAiWatch):
    def _create_model(self):
        return MaskablePPO.load(MODEL_PATH)
