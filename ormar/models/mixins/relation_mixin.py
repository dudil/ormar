import inspect
from typing import List, Optional, Set, TYPE_CHECKING, Type, Union


class RelationMixin:
    """
    Used to return relation fields/names etc. from given model
    """

    if TYPE_CHECKING:  # pragma no cover
        from ormar import ModelMeta, Model

        Meta: ModelMeta
        _related_names: Optional[Set]
        _related_fields: Optional[List]

    @classmethod
    def extract_db_own_fields(cls) -> Set:
        """
        Returns only fields that are stored in the own database table, exclude all
        related fields.
        :return: set of model fields with relation fields excluded
        :rtype: Set
        """
        related_names = cls.extract_related_names()
        self_fields = {
            name for name in cls.Meta.model_fields.keys() if name not in related_names
        }
        return self_fields

    @classmethod
    def extract_related_fields(cls) -> List:
        """
        Returns List of ormar Fields for all relations declared on a model.
        List is cached in cls._related_fields for quicker access.

        :return: list of related fields
        :rtype: List
        """
        if isinstance(cls._related_fields, List):
            return cls._related_fields

        related_fields = []
        for name in cls.extract_related_names().union(cls.extract_through_names()):
            related_fields.append(cls.Meta.model_fields[name])
        cls._related_fields = related_fields

        return related_fields

    @classmethod
    def extract_through_names(cls) -> Set:
        """
        Extracts related fields through names which are shortcuts to through models.

        :return: set of related through fields names
        :rtype: Set
        """
        related_fields = set()
        for name in cls.extract_related_names():
            field = cls.Meta.model_fields[name]
            if field.is_multi:
                related_fields.add(field.through.get_name(lower=True))
        return related_fields

    @classmethod
    def extract_related_names(cls) -> Set[str]:
        """
        Returns List of fields names for all relations declared on a model.
        List is cached in cls._related_names for quicker access.

        :return: set of related fields names
        :rtype: Set
        """
        if isinstance(cls._related_names, Set):
            return cls._related_names

        related_names = set()
        for name, field in cls.Meta.model_fields.items():
            if inspect.isclass(field) and field.is_relation and not field.is_through:
                related_names.add(name)
        cls._related_names = related_names

        return related_names

    @classmethod
    def _extract_db_related_names(cls) -> Set:
        """
        Returns only fields that are stored in the own database table, exclude
        related fields that are not stored as foreign keys on given model.
        :return: set of model fields with non fk relation fields excluded
        :rtype: Set
        """
        related_names = cls.extract_related_names()
        related_names = {
            name
            for name in related_names
            if cls.Meta.model_fields[name].is_valid_uni_relation()
        }
        return related_names

    @classmethod
    def _exclude_related_names_not_required(cls, nested: bool = False) -> Set:
        """
        Returns a set of non mandatory related models field names.

        For a main model (not nested) only nullable related field names are returned,
        for nested models all related models are returned.

        :param nested: flag setting nested models (child of previous one, not main one)
        :type nested: bool
        :return: set of non mandatory related fields
        :rtype: Set
        """
        if nested:
            return cls.extract_related_names()
        related_names = cls.extract_related_names()
        related_names = {
            name for name in related_names if cls.Meta.model_fields[name].nullable
        }
        return related_names

    @classmethod
    def _iterate_related_models(
        cls,
        visited: Set[Union[Type["Model"], Type["RelationMixin"]]] = None,
        source_relation: str = None,
        source_model: Union[Type["Model"], Type["RelationMixin"]] = None,
    ) -> List[str]:
        """
        Iterates related models recursively to extract relation strings of
        nested not visited models.

        :param visited: set of already visited models
        :type visited: Set[str]
        :param source_relation: name of the current relation
        :type source_relation: str
        :param source_model: model from which relation comes in nested relations
        :type source_model: Type["Model"]
        :return: list of relation strings to be passed to select_related
        :rtype: List[str]
        """
        visited = visited or set()
        visited.add(cls)
        relations = cls.extract_related_names()
        processed_relations = []
        for relation in relations:
            target_model = cls.Meta.model_fields[relation].to
            if source_model and target_model == source_model:
                continue
            if target_model not in visited:
                visited.add(target_model)
                deep_relations = target_model._iterate_related_models(
                    visited=visited, source_relation=relation, source_model=cls
                )
                processed_relations.extend(deep_relations)
            # TODO add test for circular deps
            else:  # pragma: no cover
                processed_relations.append(relation)
        if processed_relations:
            final_relations = [
                f"{source_relation + '__' if source_relation else ''}{relation}"
                for relation in processed_relations
            ]
        else:
            final_relations = [source_relation] if source_relation else []

        return final_relations
