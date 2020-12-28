from typing import Optional, Callable
from enum import IntEnum

class Level(IntEnum):
    GLOBAL = 0,
    DEBUG = 10,
    INFO = 20,
    WARNING = 30,
    ERROR = 40

_global_log_level = Level.INFO

def set_log_level(level: Level):
    global _global_log_level
    _global_log_level = level

class Logger:
    def __init__(self, name: str, level: Optional[Level] = Level.GLOBAL, log_func: Callable[..., None] = print):
        self.name_ = name
        self.level_ = level
        self.log_func_ = log_func

    def debug(self, *args, **kwargs):
        level = _global_log_level if self.level_ == Level.GLOBAL else self.level_
        if level <= Level.DEBUG:
            self.log_func_(self.name_+':', *args, **kwargs)

    def info(self, *args, **kwargs):
        level = _global_log_level if self.level_ == Level.GLOBAL else self.level_
        if level <= Level.INFO:
            self.log_func_(self.name_+':', *args, **kwargs)

    def warning(self, *args, **kwargs):
        level = _global_log_level if self.level_ == Level.GLOBAL else self.level_
        if level <= Level.WARNING:
            self.log_func_(self.name_+':', *args, **kwargs)

    def error(self, *args, **kwargs):
        level = _global_log_level if self.level_ == Level.GLOBAL else self.level_
        if level <= Level.ERROR:
            self.log_func_(self.name_+':', *args, **kwargs)
