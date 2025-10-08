"""
Tests for Supervisor Agent - Level 3 Enhancement
"""

import pytest
import asyncio
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.core.supervisor_agent import SupervisorAgent, get_supervisor, reset_supervisor


class TestSupervisorAgent:
    """Test suite for Supervisor Agent"""
    
    def setup_method(self):
        """Reset supervisor before each test"""
        reset_supervisor()
    
    @pytest.mark.asyncio
    async def test_simple_fact_detection(self):
        """Test detection of simple factual queries"""
        supervisor = SupervisorAgent()
        
        queries = [
            "What OS is running on server app-01?",
            "List all databases in the project",
            "Show me the application dependencies",
            "Find server with IP 10.0.1.5"
        ]
        
        for query in queries:
            result = await supervisor.analyze_intent(query)
            assert result["intent_type"] == "simple_fact"
            assert result["confidence"] > 0.6
            assert len(result["required_domains"]) >= 1
            print(f"✓ Simple fact detected: {query[:50]}... -> {result['intent_type']}")
    
    @pytest.mark.asyncio
    async def test_focused_analysis_detection(self):
        """Test detection of focused analysis queries"""
        supervisor = SupervisorAgent()
        
        queries = [
            "What are the security risks for application X?",
            "Estimate the cost for rehosting these servers",
            "Analyze the dependencies for migration wave 1",
            "Review compliance requirements for this workload"
        ]
        
        for query in queries:
            result = await supervisor.analyze_intent(query)
            assert result["intent_type"] in ["focused_analysis", "comprehensive_assessment"]
            assert result["confidence"] > 0.5
            assert len(result["required_domains"]) >= 1
            print(f"✓ Focused analysis detected: {query[:50]}... -> {result['intent_type']}")
    
    @pytest.mark.asyncio
    async def test_comprehensive_assessment_detection(self):
        """Test detection of comprehensive assessment queries"""
        supervisor = SupervisorAgent()
        
        queries = [
            "Generate a complete migration plan for this project",
            "Perform full risk assessment across all applications",
            "Create comprehensive architecture redesign recommendations",
            "Analyze end-to-end migration strategy with cost and timeline"
        ]
        
        for query in queries:
            result = await supervisor.analyze_intent(query)
            assert result["intent_type"] == "comprehensive_assessment"
            assert result["confidence"] > 0.6
            # Some comprehensive queries may have 1 domain if generic - that's OK
            assert len(result["required_domains"]) >= 1
            print(f"✓ Comprehensive detected: {query[:50]}... -> {result['intent_type']} (domains: {len(result['required_domains'])})")
    
    @pytest.mark.asyncio
    async def test_domain_detection(self):
        """Test correct domain expert selection"""
        supervisor = SupervisorAgent()
        
        test_cases = [
            ("What are the security compliance requirements?", "security_expert"),
            ("Estimate migration costs and ROI", "cost_optimizer"),
            ("Design a CI/CD pipeline for deployment", "devops_expert"),
            ("Plan database migration from Oracle to PostgreSQL", "data_expert"),
            ("Recommend application refactoring strategy", "app_modernization"),
        ]
        
        for query, expected_domain in test_cases:
            result = await supervisor.analyze_intent(query)
            assert expected_domain in result["required_domains"], \
                f"Expected {expected_domain} in {result['required_domains']} for query: {query}"
            print(f"✓ Domain detected: {query[:50]}... -> {result['required_domains']}")
    
    @pytest.mark.asyncio
    async def test_routing_decision(self):
        """Test routing decisions based on intent"""
        supervisor = SupervisorAgent()
        
        # Simple fact routing
        intent = await supervisor.analyze_intent("What is the OS of server X?")
        routing = await supervisor.route_query("What is the OS of server X?", intent)
        assert routing["execution_path"] == "direct_service_call"
        assert routing["service"] in ["graph_service", "knowledge_service"]
        assert len(routing["agents_selected"]) == 0
        print(f"✓ Simple fact routed to: {routing['service']}")
        
        # Focused analysis routing
        intent = await supervisor.analyze_intent("What are security risks for app Y?")
        routing = await supervisor.route_query("What are security risks for app Y?", intent)
        assert routing["execution_path"] == "mini_crew"
        assert len(routing["agents_selected"]) <= 2
        print(f"✓ Focused analysis routed to mini_crew with agents: {routing['agents_selected']}")
        
        # Comprehensive routing
        intent = await supervisor.analyze_intent("Generate complete migration plan")
        routing = await supervisor.route_query("Generate complete migration plan", intent)
        assert routing["execution_path"] == "full_assessment_crew"
        assert len(routing["agents_selected"]) >= 3
        print(f"✓ Comprehensive routed to full crew with {len(routing['agents_selected'])} agents")
    
    @pytest.mark.asyncio
    async def test_routing_statistics(self):
        """Test routing statistics tracking"""
        supervisor = SupervisorAgent()
        
        # Generate some routing decisions
        queries = [
            "What OS?",
            "List servers",
            "Analyze security",
            "Generate plan"
        ]
        
        for query in queries:
            await supervisor.analyze_intent(query)
        
        stats = supervisor.get_routing_statistics()
        assert stats["total_queries"] == 4
        assert "intent_distribution" in stats
        assert stats["average_confidence"] > 0
        print(f"✓ Statistics: {stats}")
    
    @pytest.mark.asyncio
    async def test_context_with_project_metadata(self):
        """Test intent analysis with project context"""
        supervisor = SupervisorAgent()
        
        context = {
            "project_name": "E-commerce Migration",
            "current_infrastructure": "On-premise VMware",
            "target_cloud": "AWS",
            "timeline": "6 months",
            "budget": "$500K"
        }
        
        query = "What migration strategy should we use?"
        result = await supervisor.analyze_intent(query, context)
        
        assert result["intent_type"] in ["focused_analysis", "comprehensive_assessment"]
        assert result["confidence"] > 0.5
        print(f"✓ Context-aware analysis: {result}")
    
    def test_singleton_pattern(self):
        """Test supervisor singleton pattern"""
        supervisor1 = get_supervisor()
        supervisor2 = get_supervisor()
        
        assert supervisor1 is supervisor2
        print("✓ Singleton pattern working")
        
        # Reset and verify new instance
        reset_supervisor()
        supervisor3 = get_supervisor()
        assert supervisor3 is not supervisor1
        print("✓ Reset creates new instance")


if __name__ == "__main__":
    """Run tests directly"""
    import sys
    
    print("=" * 80)
    print("SUPERVISOR AGENT TESTS")
    print("=" * 80)
    
    test = TestSupervisorAgent()
    
    # Run tests
    tests = [
        ("Simple Fact Detection", test.test_simple_fact_detection),
        ("Focused Analysis Detection", test.test_focused_analysis_detection),
        ("Comprehensive Assessment Detection", test.test_comprehensive_assessment_detection),
        ("Domain Detection", test.test_domain_detection),
        ("Routing Decision", test.test_routing_decision),
        ("Routing Statistics", test.test_routing_statistics),
        ("Context Awareness", test.test_context_with_project_metadata),
        ("Singleton Pattern", test.test_singleton_pattern),
    ]
    
    passed = 0
    failed = 0
    
    for name, test_func in tests:
        test.setup_method()
        print(f"\n{'─' * 80}")
        print(f"TEST: {name}")
        print(f"{'─' * 80}")
        try:
            if asyncio.iscoroutinefunction(test_func):
                asyncio.run(test_func())
            else:
                test_func()
            print(f"✅ PASSED: {name}")
            passed += 1
        except Exception as e:
            print(f"❌ FAILED: {name}")
            print(f"Error: {e}")
            import traceback
            traceback.print_exc()
            failed += 1
    
    print(f"\n{'=' * 80}")
    print(f"RESULTS: {passed} passed, {failed} failed out of {len(tests)} tests")
    print(f"{'=' * 80}")
    
    sys.exit(0 if failed == 0 else 1)
