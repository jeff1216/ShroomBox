from sb3_contrib import MaskablePPO

from fruitbox_pygame.vs import FruitBoxVs
from ._resource import resource_path

MODEL_PATH = resource_path("fruitbox_ppo_final")


class TorchVs(FruitBoxVs):
    def _create_model(self):
        return MaskablePPO.load(MODEL_PATH)
