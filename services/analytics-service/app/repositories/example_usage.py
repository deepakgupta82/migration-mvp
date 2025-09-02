"""
Example usage of AnalysisResultRepository.

This file demonstrates how to use the AnalysisResultRepository
for common analysis operations.
"""

from typing import Dict, Any
import asyncio
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy import create_engine

from .analysis_result_repository import AnalysisResultRepository
from .sql_analysis_result_repository import SqlAnalysisResultRepository
from ..models.analysis_models import (
    AnalysisResultCreate, AnalysisBatchCreate, AnalysisVersionCreate
)


class AnalysisService:
    """
    Example service demonstrating usage of AnalysisResultRepository.

    This service shows how to perform common analysis operations
    using the repository pattern.
    """

    def __init__(self, repository: AnalysisResultRepository):
        self.repository = repository

    async def create_analysis_version(self, version_number: str, description: str = None) -> str:
        """Create a new analysis version."""
        version_data = AnalysisVersionCreate(
            version_number=version_number,
            description=description
        )
        version = await self.repository.create_version(version_data)
        return version.id

    async def create_analysis_batch(self, version_id: str, batch_name: str) -> str:
        """Create a new analysis batch for a version."""
        batch_data = AnalysisBatchCreate(
            version_id=version_id,
            batch_name=batch_name,
            status="processing"
        )
        batch = await self.repository.create_batch(batch_data)
        return batch.id

    async def process_analysis_results(self, batch_id: str, results: list) -> list:
        """Process and store analysis results in batch."""
        result_creates = []
        for i, result in enumerate(results):
            result_data = AnalysisResultCreate(
                batch_id=batch_id,
                result_data=result,
                line_number=i + 1,
                status="processed"
            )
            result_creates.append(result_data)

        # Batch create all results
        created_results = await self.repository.batch_create_results(result_creates)
        return [r.id for r in created_results]

    async def get_analysis_summary(self, batch_id: str) -> Dict[str, Any]:
        """Get summary of analysis results for a batch."""
        results = await self.repository.get_results_by_batch(batch_id)
        total_count = await self.repository.get_results_count_by_batch(batch_id)

        summary = {
            "batch_id": batch_id,
            "total_results": total_count,
            "processed_results": len([r for r in results if r.status == "processed"]),
            "failed_results": len([r for r in results if r.status == "failed"]),
            "results": results
        }

        return summary

    async def update_result_status(self, result_id: str, status: str) -> None:
        """Update the status of a specific analysis result."""
        await self.repository.update_result(result_id, {"status": status})

    async def cleanup_failed_results(self, batch_id: str) -> int:
        """Remove all failed results from a batch."""
        results = await self.repository.get_results_by_batch(batch_id)
        failed_results = [r for r in results if r.status == "failed"]

        if failed_results:
            result_ids = [r.id for r in failed_results]
            await self.repository.batch_delete_results(result_ids)

        return len(failed_results)


# Example usage function
async def example_workflow():
    """
    Example workflow demonstrating the repository usage.

    Note: This is a conceptual example. In real usage, you would:
    1. Set up proper database connection
    2. Handle exceptions appropriately
    3. Use dependency injection for the repository
    """

    # This would typically come from dependency injection
    # For this example, we'll show the structure

    # Create repository (normally injected)
    # repository = SqlAnalysisResultRepository(session_factory)
    # service = AnalysisService(repository)

    # Example workflow:
    # 1. Create version
    # version_id = await service.create_analysis_version("1.0.0", "Initial analysis version")

    # 2. Create batch
    # batch_id = await service.create_analysis_batch(version_id, "Document Analysis Batch 1")

    # 3. Process results
    # sample_results = [
    #     {"document_id": "doc1", "sentiment": "positive", "confidence": 0.95},
    #     {"document_id": "doc2", "sentiment": "negative", "confidence": 0.87},
    #     {"document_id": "doc3", "sentiment": "neutral", "confidence": 0.92}
    # ]
    # result_ids = await service.process_analysis_results(batch_id, sample_results)

    # 4. Get summary
    # summary = await service.get_analysis_summary(batch_id)
    # print(f"Processed {summary['total_results']} results")

    # 5. Update status if needed
    # await service.update_result_status(result_ids[0], "completed")

    # 6. Cleanup if needed
    # failed_count = await service.cleanup_failed_results(batch_id)
    # print(f"Cleaned up {failed_count} failed results")

    print("Analysis workflow example completed (commented out for demonstration)")


if __name__ == "__main__":
    # Run example (would need proper setup)
    asyncio.run(example_workflow())