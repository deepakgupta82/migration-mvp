"""
LLM Configuration repository for database operations
"""

from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session

from .base_repository import SQLAlchemyRepository, NotFoundError
from database import LLMConfigurationModel, ModelCacheModel


class LLMConfigurationRepository(SQLAlchemyRepository[LLMConfigurationModel]):
    """Repository for LLM Configuration entities"""

    def __init__(self, session_factory):
        super().__init__(session_factory, LLMConfigurationModel)

    def get_by_provider(self, provider: str) -> List[LLMConfigurationModel]:
        """Get configurations by provider"""
        session = self._get_session()
        try:
            configs = session.query(LLMConfigurationModel).filter(
                LLMConfigurationModel.provider == provider
            ).all()

            session.expunge_all()
            return configs
        finally:
            session.close()

    def get_by_api_key_id(self, api_key_id: str) -> Optional[LLMConfigurationModel]:
        """Get configuration by API key ID"""
        session = self._get_session()
        try:
            config = session.query(LLMConfigurationModel).filter(
                LLMConfigurationModel.id == api_key_id
            ).first()

            if config:
                session.expunge(config)
            return config
        finally:
            session.close()

    def get_active_configs(self) -> List[LLMConfigurationModel]:
        """Get all active configurations"""
        session = self._get_session()
        try:
            configs = session.query(LLMConfigurationModel).filter(
                LLMConfigurationModel.id.isnot(None)  # Assuming active means has ID
            ).all()

            session.expunge_all()
            return configs
        finally:
            session.close()

    def search_configs(self, query: str) -> List[LLMConfigurationModel]:
        """Search configurations by name or provider"""
        from sqlalchemy import or_

        session = self._get_session()
        try:
            configs = session.query(LLMConfigurationModel).filter(
                or_(
                    LLMConfigurationModel.name.ilike(f"%{query}%"),
                    LLMConfigurationModel.provider.ilike(f"%{query}%"),
                    LLMConfigurationModel.model.ilike(f"%{query}%")
                )
            ).all()

            session.expunge_all()
            return configs
        finally:
            session.close()

    def is_api_key_used(self, api_key_id: str) -> bool:
        """Check if API key is used by any projects"""
        from database import ProjectModel

        session = self._get_session()
        try:
            count = session.query(ProjectModel).filter(
                ProjectModel.llm_api_key_id == api_key_id
            ).count()
            return count > 0
        finally:
            session.close()

    def delete_safe(self, config_id: str) -> bool:
        """Delete configuration only if not used by projects"""
        if self.is_api_key_used(config_id):
            raise ValidationError(f"Cannot delete LLM configuration {config_id} - it is used by projects")

        return self.delete(config_id)


class ModelCacheRepository(SQLAlchemyRepository[ModelCacheModel]):
    """Repository for Model Cache entities"""

    def __init__(self, session_factory):
        super().__init__(session_factory, ModelCacheModel)

    def get_by_provider(self, provider: str) -> List[ModelCacheModel]:
        """Get cached models by provider"""
        session = self._get_session()
        try:
            models = session.query(ModelCacheModel).filter(
                ModelCacheModel.provider == provider.lower(),
                ModelCacheModel.is_active == True
            ).all()

            session.expunge_all()
            return models
        finally:
            session.close()

    def get_active_providers(self) -> List[str]:
        """Get list of providers with active models"""
        session = self._get_session()
        try:
            from sqlalchemy import distinct

            providers = session.query(distinct(ModelCacheModel.provider)).filter(
                ModelCacheModel.is_active == True
            ).all()

            return [p[0] for p in providers]
        finally:
            session.close()

    def clear_provider_cache(self, provider: str) -> int:
        """Clear all cached models for a provider"""
        session = self._get_session()
        try:
            def _clear(sess):
                count = sess.query(ModelCacheModel).filter(
                    ModelCacheModel.provider == provider.lower()
                ).delete()
                return count

            return self._execute_in_transaction(_clear)
        finally:
            session.close()

    def cache_models_bulk(self, provider: str, models_data: List[Dict[str, Any]]) -> int:
        """Cache multiple models for a provider"""
        session = self._get_session()
        try:
            def _cache_bulk(sess):
                # Clear existing cache for provider
                sess.query(ModelCacheModel).filter(
                    ModelCacheModel.provider == provider.lower()
                ).delete()

                # Add new models
                count = 0
                for model_data in models_data:
                    cache_entry = ModelCacheModel(
                        id=f"{provider.lower()}_{model_data['id']}",
                        provider=provider.lower(),
                        model_id=model_data["id"],
                        model_name=model_data.get("name", model_data["id"]),
                        description=model_data.get("description"),
                        is_active=True
                    )
                    sess.add(cache_entry)
                    count += 1

                return count

            return self._execute_in_transaction(_cache_bulk)
        finally:
            session.close()