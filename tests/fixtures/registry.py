from polyfactory.factories.pydantic_factory import ModelFactory

from taken.models.registry import RegistryEntry


class RegistryEntryFactory(ModelFactory[RegistryEntry]):
    __model__ = RegistryEntry
