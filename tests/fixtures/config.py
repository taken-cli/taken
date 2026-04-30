from polyfactory.factories.pydantic_factory import ModelFactory

from taken.models.config import TakenConfig


class TakenConfigFactory(ModelFactory[TakenConfig]):
    __model__ = TakenConfig
