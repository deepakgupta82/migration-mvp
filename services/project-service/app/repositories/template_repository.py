"""
Template repository for database operations
"""

from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session

from .base_repository import SQLAlchemyRepository
from database import DeliverableTemplateModel, TemplateUsageModel, GenerationRequestModel


class DeliverableTemplateRepository(SQLAlchemyRepository[DeliverableTemplateModel]):
    """Repository for Deliverable Template entities"""

    def __init__(self, session_factory):
        super().__init__(session_factory, DeliverableTemplateModel)

    def get_global_templates(self) -> List[DeliverableTemplateModel]:
        """Get all global templates"""
        session = self._get_session()
        try:
            templates = session.query(DeliverableTemplateModel).filter(
                DeliverableTemplateModel.template_type == "global",
                DeliverableTemplateModel.is_active == True
            ).all()

            session.expunge_all()
            return templates
        finally:
            session.close()

    def get_project_templates(self, project_id: str) -> List[DeliverableTemplateModel]:
        """Get templates for a specific project"""
        session = self._get_session()
        try:
            templates = session.query(DeliverableTemplateModel).filter(
                DeliverableTemplateModel.project_id == project_id,
                DeliverableTemplateModel.template_type == "project"
            ).all()

            session.expunge_all()
            return templates
        finally:
            session.close()

    def get_all_available_templates(self, project_id: str) -> Dict[str, List[DeliverableTemplateModel]]:
        """Get both global and project-specific templates"""
        return {
            "global_templates": self.get_global_templates(),
            "project_templates": self.get_project_templates(project_id)
        }

    def search_templates(self, query: str, project_id: Optional[str] = None) -> List[DeliverableTemplateModel]:
        """Search templates by name or description"""
        from sqlalchemy import or_

        session = self._get_session()
        try:
            base_query = session.query(DeliverableTemplateModel).filter(
                DeliverableTemplateModel.is_active == True,
                or_(
                    DeliverableTemplateModel.name.ilike(f"%{query}%"),
                    DeliverableTemplateModel.description.ilike(f"%{query}%")
                )
            )

            if project_id:
                base_query = base_query.filter(
                    or_(
                        DeliverableTemplateModel.project_id == project_id,
                        DeliverableTemplateModel.template_type == "global"
                    )
                )
            else:
                base_query = base_query.filter(
                    DeliverableTemplateModel.template_type == "global"
                )

            templates = base_query.all()
            session.expunge_all()
            return templates
        finally:
            session.close()

    def increment_usage_count(self, template_id: str) -> Optional[DeliverableTemplateModel]:
        """Increment usage count for a template"""
        session = self._get_session()
        try:
            def _increment(sess):
                template = sess.query(DeliverableTemplateModel).filter(
                    DeliverableTemplateModel.id == template_id
                ).first()

                if template:
                    template.usage_count = (template.usage_count or 0) + 1
                    template.last_used = sess.query(DeliverableTemplateModel).filter(
                        DeliverableTemplateModel.id == template_id
                    ).first().last_used  # This should be current timestamp

                return template

            return self._execute_in_transaction(_increment)
        finally:
            session.close()


class TemplateUsageRepository(SQLAlchemyRepository[TemplateUsageModel]):
    """Repository for Template Usage entities"""

    def __init__(self, session_factory):
        super().__init__(session_factory, TemplateUsageModel)

    def get_project_usage(self, project_id: str) -> List[TemplateUsageModel]:
        """Get usage history for a project"""
        session = self._get_session()
        try:
            usage = session.query(TemplateUsageModel).filter(
                TemplateUsageModel.project_id == project_id
            ).order_by(TemplateUsageModel.used_at.desc()).all()

            session.expunge_all()
            return usage
        finally:
            session.close()

    def get_template_usage_stats(self, template_name: str, template_type: str) -> Dict[str, Any]:
        """Get usage statistics for a template"""
        from sqlalchemy import func

        session = self._get_session()
        try:
            stats = session.query(
                func.count(TemplateUsageModel.id).label('total_usage'),
                func.count(func.distinct(TemplateUsageModel.project_id)).label('projects_used'),
                func.max(TemplateUsageModel.used_at).label('last_used')
            ).filter(
                TemplateUsageModel.template_name == template_name,
                TemplateUsageModel.template_type == template_type
            ).first()

            return {
                "total_usage": stats.total_usage or 0,
                "projects_used": stats.projects_used or 0,
                "last_used": stats.last_used
            }
        finally:
            session.close()

    def get_global_usage_stats(self) -> List[Dict[str, Any]]:
        """Get usage statistics for all templates"""
        from sqlalchemy import func

        session = self._get_session()
        try:
            stats = session.query(
                TemplateUsageModel.template_name,
                TemplateUsageModel.template_type,
                func.count(TemplateUsageModel.id).label('total_usage'),
                func.count(func.distinct(TemplateUsageModel.project_id)).label('projects_used'),
                func.max(TemplateUsageModel.used_at).label('last_used')
            ).group_by(
                TemplateUsageModel.template_name,
                TemplateUsageModel.template_type
            ).all()

            return [{
                "template_name": stat.template_name,
                "template_type": stat.template_type,
                "total_usage": stat.total_usage,
                "projects_used": stat.projects_used,
                "last_used": stat.last_used
            } for stat in stats]
        finally:
            session.close()


class GenerationRequestRepository(SQLAlchemyRepository[GenerationRequestModel]):
    """Repository for Generation Request entities"""

    def __init__(self, session_factory):
        super().__init__(session_factory, GenerationRequestModel)

    def get_project_requests(self, project_id: str) -> List[GenerationRequestModel]:
        """Get generation requests for a project"""
        session = self._get_session()
        try:
            requests = session.query(GenerationRequestModel).filter(
                GenerationRequestModel.project_id == project_id
            ).order_by(GenerationRequestModel.requested_at.desc()).all()

            session.expunge_all()
            return requests
        finally:
            session.close()

    def get_pending_requests(self) -> List[GenerationRequestModel]:
        """Get all pending generation requests"""
        session = self._get_session()
        try:
            requests = session.query(GenerationRequestModel).filter(
                GenerationRequestModel.status == "pending"
            ).order_by(GenerationRequestModel.requested_at).all()

            session.expunge_all()
            return requests
        finally:
            session.close()

    def update_request_status(self, request_id: str, status: str, **kwargs) -> Optional[GenerationRequestModel]:
        """Update request status with additional fields"""
        updates = {"status": status}
        updates.update(kwargs)
        return self.update(request_id, updates)