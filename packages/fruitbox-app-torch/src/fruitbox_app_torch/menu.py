from fruitbox_pygame.menu import FruitBoxMenu

from .ai_watch import TorchAiWatch
from .vs import TorchVs


class TorchMenu(FruitBoxMenu):
    vs_class = TorchVs
    watch_class = TorchAiWatch
    model_opponent = "rl_model"
