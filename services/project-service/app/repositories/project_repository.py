"""
Project repository for database operations
"""

from typing import List, Optional, Dict, Any
from uuid import UUID
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import and_, or_

from .base_repository import SQLAlchemyRepository, NotFoundError
from database import ProjectModel, UserModel, ProjectFileModel


class ProjectRepository(SQLAlchemyRepository[ProjectModel]):
    """Repository for Project entities"""

    def __init__(self, session_factory):
        super().__init__(session_factory, ProjectModel)

    def get_by_id_with_users(self, project_id: str) -> Optional[ProjectModel]:
        """Get project by ID with users loaded"""
        session = self._get_session()
        try:
            project = session.query(ProjectModel).options(
                joinedload(ProjectModel.users)
            ).filter(ProjectModel.id == project_id).first()

            if project:
                session.expunge_all()
            return project
        finally:
            session.close()

    def get_by_id_with_files(self, project_id: str) -> Optional[ProjectModel]:
        """Get project by ID with files loaded"""
        session = self._get_session()
        try:
            project = session.query(ProjectModel).options(
                joinedload(ProjectModel.files)
            ).filter(ProjectModel.id == project_id).first()

            if project:
                session.expunge_all()
            return project
        finally:
            session.close()

    def get_user_projects(self, user_id: str) -> List[ProjectModel]:
        """Get all projects for a user"""
        session = self._get_session()
        try:
            projects = session.query(ProjectModel).join(
                ProjectModel.users
            ).filter(UserModel.id == user_id).all()

            session.expunge_all()
            return projects
        finally:
            session.close()

    def get_projects_by_status(self, status: str) -> List[ProjectModel]:
        """Get projects by status"""
        session = self._get_session()
        try:
            projects = session.query(ProjectModel).filter(
                ProjectModel.status == status
            ).order_by(ProjectModel.created_at.desc()).all()

            session.expunge_all()
            return projects
        finally:
            session.close()

    def search_projects(self, query: str, user_id: Optional[str] = None) -> List[ProjectModel]:
        """Search projects by name or description"""
        session = self._get_session()
        try:
            base_query = session.query(ProjectModel).filter(
                or_(
                    ProjectModel.name.ilike(f"%{query}%"),
                    ProjectModel.description.ilike(f"%{query}%"),
                    ProjectModel.client_name.ilike(f"%{query}%")
                )
            )

            if user_id:
                base_query = base_query.join(ProjectModel.users).filter(UserModel.id == user_id)

            projects = base_query.order_by(ProjectModel.created_at.desc()).all()
            session.expunge_all()
            return projects
        finally:
            session.close()

    def get_project_stats(self, user_id: Optional[str] = None) -> Dict[str, int]:
        """Get project statistics"""
        session = self._get_session()
        try:
            base_query = session.query(ProjectModel)

            if user_id:
                base_query = base_query.join(ProjectModel.users).filter(UserModel.id == user_id)

            total = base_query.count()
            active = base_query.filter(ProjectModel.status.in_(["initiated", "running"])).count()
            completed = base_query.filter(ProjectModel.status == "completed").count()

            return {
                "total_projects": total,
                "active_projects": active,
                "completed_assessments": completed
            }
        finally:
            session.close()

    def update_project_status(self, project_id: str, status: str) -> Optional[ProjectModel]:
        """Update project status"""
        return self.update(project_id, {"status": status})

    def add_user_to_project(self, project_id: str, user_id: str) -> bool:
        """Add user to project"""
        session = self._get_session()
        try:
            def _add_user(sess):
                project = sess.query(ProjectModel).filter(ProjectModel.id == project_id).first()
                user = sess.query(UserModel).filter(UserModel.id == user_id).first()

                if not project or not user:
                    return False

                if user not in project.users:
                    project.users.append(user)

                return True

            return self._execute_in_transaction(_add_user)
        finally:
            session.close()

    def remove_user_from_project(self, project_id: str, user_id: str) -> bool:
        """Remove user from project"""
        session = self._get_session()
        try:
            def _remove_user(sess):
                project = sess.query(ProjectModel).filter(ProjectModel.id == project_id).first()
                user = sess.query(UserModel).filter(UserModel.id == user_id).first()

                if not project or not user:
                    return False

                if user in project.users:
                    project.users.remove(user)

                return True

            return self._execute_in_transaction(_remove_user)
        finally:
            session.close()

    def get_project_files_count(self, project_id: str) -> int:
        """Get count of files for a project"""
        session = self._get_session()
        try:
            count = session.query(ProjectFileModel).filter(
                ProjectFileModel.project_id == project_id
            ).count()
            return count
        finally:
            session.close()

    def delete_project_cascade(self, project_id: str) -> bool:
        """Delete project and all related data"""
        session = self._get_session()
        try:
            def _delete_cascade(sess):
                project = sess.query(ProjectModel).filter(ProjectModel.id == project_id).first()
                if not project:
                    return False

                # Delete associated files
                sess.query(ProjectFileModel).filter(ProjectFileModel.project_id == project_id).delete()

                # Delete the project (cascade will handle relationships)
                sess.delete(project)
                return True

            return self._execute_in_transaction(_delete_cascade)
        finally:
            session.close()


class UserRepository(SQLAlchemyRepository[UserModel]):
    """Repository for User entities"""

    def __init__(self, session_factory):
        super().__init__(session_factory, UserModel)

    def get_by_email(self, email: str) -> Optional[UserModel]:
        """Get user by email"""
        session = self._get_session()
        try:
            user = session.query(UserModel).filter(UserModel.email == email).first()
            if user:
                session.expunge(user)
            return user
        finally:
            session.close()

    def get_active_users(self) -> List[UserModel]:
        """Get all active users"""
        session = self._get_session()
        try:
            users = session.query(UserModel).filter(UserModel.is_active == True).all()
            session.expunge_all()
            return users
        finally:
            session.close()

    def search_users(self, query: str) -> List[UserModel]:
        """Search users by email, username, or name"""
        session = self._get_session()
        try:
            users = session.query(UserModel).filter(
                and_(
                    UserModel.is_active == True,
                    or_(
                        UserModel.email.ilike(f"%{query}%"),
                        UserModel.username.ilike(f"%{query}%"),
                        UserModel.first_name.ilike(f"%{query}%"),
                        UserModel.last_name.ilike(f"%{query}%")
                    )
                )
            ).all()

            session.expunge_all()
            return users
        finally:
            session.close()

    def update_last_login(self, user_id: str) -> Optional[UserModel]:
        """Update user's last login timestamp"""
        from datetime import datetime
        return self.update(user_id, {"last_login": datetime.utcnow()})

    def get_user_projects_count(self, user_id: str) -> int:
        """Get count of projects for a user"""
        session = self._get_session()
        try:
            user = session.query(UserModel).options(
                joinedload(UserModel.projects)
            ).filter(UserModel.id == user_id).first()

            return len(user.projects) if user else 0
        finally:
            session.close()