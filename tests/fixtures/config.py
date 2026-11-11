from polyfactory import Use
from polyfactory.factories.pydantic_factory import ModelFactory

from taken.models.config import SkillsConfig, TakenConfig


class TakenConfigFactory(ModelFactory[TakenConfig]):
    __model__ = TakenConfig

    skills = Use(SkillsConfig)
