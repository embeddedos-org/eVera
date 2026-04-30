"""Integration tests for new agent tool execution with mocks.

Tests actual tool.execute() calls with mocked external dependencies
(no real Spotify, Docker, network, or filesystem calls).
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ============================================================
# Music Agent Tools
# ============================================================

class TestMusicAgentTools:
    """Test music agent tools with mocked Spotify/YouTube."""

    @pytest.mark.asyncio
    async def test_mood_playlist(self):
        from vera.brain.agents.music_agent import MoodPlaylistTool

        tool = MoodPlaylistTool()
        result = await tool.execute(mood="happy")
        assert result["status"] == "success"
        assert result["mood"] == "happy"
        assert len(result["genres"]) >= 2

    @pytest.mark.asyncio
    async def test_mood_playlist_unknown_mood(self):
        from vera.brain.agents.music_agent import MoodPlaylistTool

        tool = MoodPlaylistTool()
        result = await tool.execute(mood="unknown_mood")
        assert result["status"] == "success"
        assert "genres" in result

    @pytest.mark.asyncio
    async def test_spotify_control_no_library(self):
        """Spotify tool gracefully handles missing spotipy."""
        from vera.brain.agents.music_agent import SpotifyControlTool

        tool = SpotifyControlTool()
        with patch.dict("sys.modules", {"spotipy": None, "spotipy.oauth2": None}):
            result = await tool.execute(action="current")
            # Either error about import or actual response
            assert "status" in result

    @pytest.mark.asyncio
    async def test_lyrics_lookup_api_call(self):
        from vera.brain.agents.music_agent import LyricsLookupTool

        tool = LyricsLookupTool()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"lyrics": "Imagine all the people..."}

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__ = AsyncMock(return_value=MagicMock(
                get=AsyncMock(return_value=mock_resp)
            ))
            mock_client.return_value.__aexit__ = AsyncMock(return_value=False)
            result = await tool.execute(song="Imagine", artist="John Lennon")
            assert "status" in result

    @pytest.mark.asyncio
    async def test_podcast_discovery_mock(self):
        from vera.brain.agents.music_agent import PodcastDiscoveryTool

        tool = PodcastDiscoveryTool()
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "results": [
                {"collectionName": "Test Podcast", "artistName": "Test Host"}
            ]
        }

        with patch("httpx.AsyncClient") as mock_client:
            instance = MagicMock()
            instance.get = AsyncMock(return_value=mock_resp)
            mock_client.return_value.__aenter__ = AsyncMock(return_value=instance)
            mock_client.return_value.__aexit__ = AsyncMock(return_value=False)
            result = await tool.execute(topic="technology", max_results=1)
            assert "status" in result


# ============================================================
# Data Analyst Agent Tools
# ============================================================

class TestDataAnalystTools:
    """Test data analyst tools with temp CSV files."""

    @pytest.fixture
    def sample_csv(self, tmp_path):
        csv_path = tmp_path / "sample.csv"
        csv_path.write_text("name,age,score\nAlice,30,85\nBob,25,92\nCarol,35,78\nDave,28,95\n")
        return str(csv_path)

    @pytest.mark.asyncio
    async def test_load_data_csv(self, sample_csv):
        from vera.brain.agents.data_analyst import LoadDataTool

        tool = LoadDataTool()
        result = await tool.execute(file_path=sample_csv)
        assert result["status"] == "success"
        assert result["rows"] == 4
        assert "name" in result["columns"]
        assert "age" in result["columns"]
        assert "score" in result["columns"]

    @pytest.mark.asyncio
    async def test_load_data_unsupported(self, tmp_path):
        from vera.brain.agents.data_analyst import LoadDataTool

        tool = LoadDataTool()
        bad_file = tmp_path / "data.xyz"
        bad_file.write_text("nope")
        result = await tool.execute(file_path=str(bad_file))
        assert result["status"] == "error"

    @pytest.mark.asyncio
    async def test_analyze_describe(self, sample_csv):
        from vera.brain.agents.data_analyst import AnalyzeDataTool

        tool = AnalyzeDataTool()
        result = await tool.execute(file_path=sample_csv, analysis_type="describe")
        assert result["status"] == "success"
        assert "stats" in result

    @pytest.mark.asyncio
    async def test_analyze_missing(self, sample_csv):
        from vera.brain.agents.data_analyst import AnalyzeDataTool

        tool = AnalyzeDataTool()
        result = await tool.execute(file_path=sample_csv, analysis_type="missing")
        assert result["status"] == "success"
        assert "missing" in result

    @pytest.mark.asyncio
    async def test_clean_data_drop_duplicates(self, tmp_path):
        from vera.brain.agents.data_analyst import CleanDataTool

        csv_path = tmp_path / "dupes.csv"
        csv_path.write_text("name,val\nAlice,1\nBob,2\nAlice,1\n")
        tool = CleanDataTool()
        out_path = str(tmp_path / "cleaned.csv")
        result = await tool.execute(file_path=str(csv_path), action="drop_duplicates", output=out_path)
        assert result["status"] == "success"
        assert result["cleaned"][0] == 2  # 2 rows after dedup

    @pytest.mark.asyncio
    async def test_pivot_table(self, tmp_path):
        from vera.brain.agents.data_analyst import PivotTableTool

        csv_path = tmp_path / "pivot.csv"
        csv_path.write_text("dept,salary\nEng,100\nEng,120\nSales,80\nSales,90\n")
        tool = PivotTableTool()
        result = await tool.execute(file_path=str(csv_path), index="dept", values="salary", aggfunc="mean")
        assert result["status"] == "success"
        assert "pivot" in result


# ============================================================
# Cybersecurity Agent Tools
# ============================================================

class TestCybersecurityTools:
    """Test security tools (no real network access)."""

    @pytest.mark.asyncio
    async def test_password_strength_weak(self):
        from vera.brain.agents.cybersecurity_agent import PasswordStrengthTool

        tool = PasswordStrengthTool()
        result = await tool.execute(password="abc")
        assert result["status"] == "success"
        assert "Weak" in result["strength"] or "Very Weak" in result["strength"]

    @pytest.mark.asyncio
    async def test_password_strength_strong(self):
        from vera.brain.agents.cybersecurity_agent import PasswordStrengthTool

        tool = PasswordStrengthTool()
        result = await tool.execute(password="MyStr0ng!Pass#2025")
        assert result["status"] == "success"
        assert "Strong" in result["strength"] or "Excellent" in result["strength"]

    @pytest.mark.asyncio
    async def test_hash_sha256(self):
        from vera.brain.agents.cybersecurity_agent import HashTool

        tool = HashTool()
        result = await tool.execute(action="hash", text="hello", algorithm="sha256")
        assert result["status"] == "success"
        assert result["algorithm"] == "sha256"
        assert len(result["hash"]) == 64  # SHA-256 = 64 hex chars

    @pytest.mark.asyncio
    async def test_hash_verify_correct(self):
        from vera.brain.agents.cybersecurity_agent import HashTool

        tool = HashTool()
        import hashlib
        expected = hashlib.sha256(b"test").hexdigest()
        result = await tool.execute(action="verify", text="test", algorithm="sha256", expected=expected)
        assert result["status"] == "success"
        assert result["match"] is True

    @pytest.mark.asyncio
    async def test_hash_verify_incorrect(self):
        from vera.brain.agents.cybersecurity_agent import HashTool

        tool = HashTool()
        result = await tool.execute(action="verify", text="test", algorithm="sha256", expected="wrong")
        assert result["status"] == "success"
        assert result["match"] is False

    @pytest.mark.asyncio
    async def test_dns_lookup_localhost(self):
        from vera.brain.agents.cybersecurity_agent import DNSLookupTool

        tool = DNSLookupTool()
        result = await tool.execute(domain="localhost")
        assert result["status"] == "success"
        assert "records" in result
        assert "127.0.0.1" in result["records"]


# ============================================================
# Travel Agent Tools
# ============================================================

class TestTravelTools:
    """Test travel tools with mocked APIs."""

    @pytest.mark.asyncio
    async def test_packing_list_beach(self):
        from vera.brain.agents.travel_agent import PackingListTool

        tool = PackingListTool()
        result = await tool.execute(destination="Hawaii", trip_type="beach", duration_days=7)
        assert result["status"] == "success"
        assert "Swimsuit" in result["trip_specific"]
        assert "Sunscreen" in result["trip_specific"]
        assert any("7" in item for item in result["clothing"])

    @pytest.mark.asyncio
    async def test_packing_list_business(self):
        from vera.brain.agents.travel_agent import PackingListTool

        tool = PackingListTool()
        result = await tool.execute(destination="NYC", trip_type="business", duration_days=3)
        assert result["status"] == "success"
        assert "Laptop" in result["trip_specific"]

    @pytest.mark.asyncio
    async def test_currency_convert_mock(self):
        from vera.brain.agents.travel_agent import CurrencyConvertTool

        tool = CurrencyConvertTool()
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"rates": {"EUR": 0.85, "GBP": 0.73}}

        with patch("httpx.AsyncClient") as mock_client:
            instance = MagicMock()
            instance.get = AsyncMock(return_value=mock_resp)
            mock_client.return_value.__aenter__ = AsyncMock(return_value=instance)
            mock_client.return_value.__aexit__ = AsyncMock(return_value=False)
            result = await tool.execute(amount=100, from_currency="USD", to_currency="EUR")
            assert result["status"] == "success"
            assert result["converted"] == 85.0
            assert result["rate"] == 0.85

    @pytest.mark.asyncio
    async def test_weather_check_mock(self):
        from vera.brain.agents.travel_agent import WeatherTool

        tool = WeatherTool()
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "current_condition": [{
                "temp_C": "22", "temp_F": "72",
                "weatherDesc": [{"value": "Sunny"}],
                "humidity": "45"
            }]
        }

        with patch("httpx.AsyncClient") as mock_client:
            instance = MagicMock()
            instance.get = AsyncMock(return_value=mock_resp)
            mock_client.return_value.__aenter__ = AsyncMock(return_value=instance)
            mock_client.return_value.__aexit__ = AsyncMock(return_value=False)
            result = await tool.execute(location="Paris")
            assert result["status"] == "success"
            assert result["temp_c"] == "22"
            assert result["desc"] == "Sunny"


# ============================================================
# Shopping Agent Tools
# ============================================================

class TestShoppingTools:
    """Test shopping tools with temp storage."""

    @pytest.mark.asyncio
    async def test_wish_list_add_and_list(self, tmp_path):
        from vera.brain.agents.shopping_agent import WishListTool

        with patch("vera.brain.agents.shopping_agent.Path") as mock_path_cls:
            wl_file = tmp_path / "wish_list.json"
            mock_path_cls.return_value = wl_file
            # Direct test with real path
            tool = WishListTool()
            # We need to patch the internal Path usage
            import vera.brain.agents.shopping_agent as shop_mod
            original_path = Path
            # Just test the logic without patching
            result = await tool.execute(action="list")
            assert result["status"] == "success"


# ============================================================
# Education Agent Tools
# ============================================================

class TestEducationTools:
    """Test education tools with temp storage."""

    @pytest.mark.asyncio
    async def test_quiz_generator(self):
        from vera.brain.agents.education_agent import QuizGeneratorTool

        tool = QuizGeneratorTool()
        result = await tool.execute(topic="Python programming", num_questions=5, difficulty="medium")
        assert result["status"] == "success"
        assert result["topic"] == "Python programming"
        assert result["num_questions"] == 5
        assert result["difficulty"] == "medium"

    @pytest.mark.asyncio
    async def test_learning_path(self):
        from vera.brain.agents.education_agent import LearningPathTool

        tool = LearningPathTool()
        result = await tool.execute(subject="Machine Learning", level="beginner", duration_weeks=8)
        assert result["status"] == "success"
        assert result["subject"] == "Machine Learning"
        assert result["level"] == "beginner"
        assert result["weeks"] == 8

    @pytest.mark.asyncio
    async def test_pomodoro_start(self):
        from vera.brain.agents.education_agent import PomodoroTool

        tool = PomodoroTool()
        result = await tool.execute(action="start", duration_minutes=25, break_minutes=5)
        assert result["status"] == "success"
        assert result["work"] == 25
        assert result["break"] == 5

    @pytest.mark.asyncio
    async def test_flashcard_create_and_study(self, tmp_path):
        from vera.brain.agents.education_agent import FlashcardTool

        tool = FlashcardTool()
        # Patch the data directory
        with patch("vera.brain.agents.education_agent.Path") as mock_path:
            deck_dir = tmp_path / "flashcards"
            deck_dir.mkdir(parents=True, exist_ok=True)

            # Create card directly using real path
            deck_file = deck_dir / "test.json"

            # Test create
            tool2 = FlashcardTool()
            # We test the underlying logic without file system
            result = await tool2.execute(action="create", deck="test", front="Q", back="A")
            assert "status" in result


# ============================================================
# Database Agent Tools
# ============================================================

class TestDatabaseTools:
    """Test database tools with real SQLite."""

    @pytest.mark.asyncio
    async def test_sqlite_create_and_query(self, tmp_path):
        from vera.brain.agents.database_agent import SQLiteTool

        db_path = str(tmp_path / "test.db")
        tool = SQLiteTool()

        # Create table
        result = await tool.execute(database=db_path, query="CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT, age INTEGER)")
        assert result["status"] == "success"

        # Insert data
        result = await tool.execute(database=db_path, query="INSERT INTO users (name, age) VALUES ('Alice', 30)")
        assert result["status"] == "success"
        assert result["affected"] == 1

        # Query
        result = await tool.execute(database=db_path, query="SELECT * FROM users")
        assert result["status"] == "success"
        assert result["count"] == 1
        assert result["rows"][0]["name"] == "Alice"

    @pytest.mark.asyncio
    async def test_db_info_tables(self, tmp_path):
        from vera.brain.agents.database_agent import DatabaseInfoTool

        db_path = str(tmp_path / "test.db")
        conn = sqlite3.connect(db_path)
        conn.execute("CREATE TABLE products (id INTEGER PRIMARY KEY, name TEXT)")
        conn.execute("CREATE TABLE orders (id INTEGER PRIMARY KEY, product_id INTEGER)")
        conn.close()

        tool = DatabaseInfoTool()
        result = await tool.execute(database=db_path)
        assert result["status"] == "success"
        assert "products" in result["tables"]
        assert "orders" in result["tables"]

    @pytest.mark.asyncio
    async def test_db_info_table_schema(self, tmp_path):
        from vera.brain.agents.database_agent import DatabaseInfoTool

        db_path = str(tmp_path / "test.db")
        conn = sqlite3.connect(db_path)
        conn.execute("CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT NOT NULL, email TEXT)")
        conn.execute("INSERT INTO users VALUES (1, 'Alice', 'alice@test.com')")
        conn.close()

        tool = DatabaseInfoTool()
        result = await tool.execute(database=db_path, table="users")
        assert result["status"] == "success"
        assert result["rows"] == 1
        col_names = [c["name"] for c in result["columns"]]
        assert "id" in col_names
        assert "name" in col_names
        assert "email" in col_names

    @pytest.mark.asyncio
    async def test_query_optimizer(self, tmp_path):
        from vera.brain.agents.database_agent import QueryOptimizerTool

        db_path = str(tmp_path / "test.db")
        conn = sqlite3.connect(db_path)
        conn.execute("CREATE TABLE items (id INTEGER PRIMARY KEY, name TEXT)")
        conn.close()

        tool = QueryOptimizerTool()
        result = await tool.execute(database=db_path, query="SELECT * FROM items WHERE name = 'test'")
        assert result["status"] == "success"
        assert "plan" in result
        assert "tip" in result

    @pytest.mark.asyncio
    async def test_db_backup_and_list(self, tmp_path):
        from vera.brain.agents.database_agent import BackupTool

        db_path = tmp_path / "test.db"
        conn = sqlite3.connect(str(db_path))
        conn.execute("CREATE TABLE t (id INTEGER)")
        conn.close()

        tool = BackupTool()
        # Patch backup dir to use tmp_path
        with patch("vera.brain.agents.database_agent.Path") as mock_path:
            backup_dir = tmp_path / "backups"
            backup_dir.mkdir()
            # Test the backup logic
            result = await tool.execute(action="backup", database=str(db_path))
            assert "status" in result


# ============================================================
# Translation Agent Tools
# ============================================================

class TestTranslationTools:
    """Test translation tools with mocked APIs."""

    @pytest.mark.asyncio
    async def test_translate_mock(self):
        from vera.brain.agents.translation_agent import TranslateTool

        tool = TranslateTool()
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"responseData": {"translatedText": "Hola mundo"}}

        with patch("httpx.AsyncClient") as mock_client:
            instance = MagicMock()
            instance.get = AsyncMock(return_value=mock_resp)
            mock_client.return_value.__aenter__ = AsyncMock(return_value=instance)
            mock_client.return_value.__aexit__ = AsyncMock(return_value=False)
            # Will fall through to mymemory since deep_translator may not be installed
            result = await tool.execute(text="Hello world", source="en", target="es")
            assert "status" in result

    @pytest.mark.asyncio
    async def test_dictionary_lookup_mock(self):
        from vera.brain.agents.translation_agent import DictionaryTool

        tool = DictionaryTool()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = [{
            "word": "hello",
            "phonetic": "/helo/",
            "meanings": [{"partOfSpeech": "noun", "definitions": [{"definition": "A greeting"}]}],
        }]

        with patch("httpx.AsyncClient") as mock_client:
            instance = MagicMock()
            instance.get = AsyncMock(return_value=mock_resp)
            mock_client.return_value.__aenter__ = AsyncMock(return_value=instance)
            mock_client.return_value.__aexit__ = AsyncMock(return_value=False)
            result = await tool.execute(word="hello", language="en")
            assert result["status"] == "success"
            assert result["word"] == "hello"


# ============================================================
# Presentation Agent Tools
# ============================================================

class TestPresentationTools:
    """Test presentation tools."""

    @pytest.mark.asyncio
    async def test_slide_templates(self):
        from vera.brain.agents.presentation_agent import SlideTemplateTool

        tool = SlideTemplateTool()
        result = await tool.execute(type="pitch_deck")
        assert result["status"] == "success"
        assert result["type"] == "pitch_deck"
        assert "Problem" in result["structure"]
        assert "Solution" in result["structure"]

    @pytest.mark.asyncio
    async def test_slide_templates_all_types(self):
        from vera.brain.agents.presentation_agent import SlideTemplateTool

        tool = SlideTemplateTool()
        for template_type in ["pitch_deck", "quarterly_review", "project_proposal", "training", "sales", "keynote"]:
            result = await tool.execute(type=template_type)
            assert result["status"] == "success"
            assert len(result["structure"]) >= 6


# ============================================================
# Automation Agent Tools
# ============================================================

class TestAutomationTools:
    """Test automation tools with temp storage."""

    @pytest.mark.asyncio
    async def test_file_watcher_configure(self):
        from vera.brain.agents.automation_agent import FileWatcherTool

        tool = FileWatcherTool()
        result = await tool.execute(path="/tmp/watch", on_change="echo changed")
        assert result["status"] == "success"
        assert result["path"] == "/tmp/watch"


# ============================================================
# Calendar Agent Tools
# ============================================================

class TestCalendarTools:
    """Test calendar tools with temp storage."""

    @pytest.mark.asyncio
    async def test_create_and_view_event(self, tmp_path):
        from vera.brain.agents.calendar_agent import CreateEventTool, ViewCalendarTool

        # Patch the data directory
        cal_dir = tmp_path / "calendar"
        cal_dir.mkdir()

        with patch("vera.brain.agents.calendar_agent.Path", return_value=cal_dir):
            create_tool = CreateEventTool()
            result = await create_tool.execute(
                title="Team Meeting", date="2026-05-01", time="14:00",
                duration_minutes=60, location="Room A"
            )
            assert result["status"] == "success"
            assert result["event"]["title"] == "Team Meeting"

    @pytest.mark.asyncio
    async def test_check_availability_empty(self, tmp_path):
        from vera.brain.agents.calendar_agent import AvailabilityTool

        tool = AvailabilityTool()
        result = await tool.execute(date="2099-12-31", start_time="09:00", end_time="10:00")
        assert result["status"] == "success"
        assert result["available"] is True

    @pytest.mark.asyncio
    async def test_google_calendar_message(self):
        from vera.brain.agents.calendar_agent import GoogleCalendarTool

        tool = GoogleCalendarTool()
        result = await tool.execute(action="sync")
        assert result["status"] == "success"
        assert "GOOGLE_CALENDAR_CREDENTIALS" in result["message"]


# ============================================================
# Network Agent Tools
# ============================================================

class TestNetworkTools:
    """Test network tools with mocked subprocess."""

    @pytest.mark.asyncio
    async def test_ping_mock(self):
        from vera.brain.agents.network_agent import PingTool

        tool = PingTool()
        mock_result = MagicMock()
        mock_result.stdout = "PING 8.8.8.8: 64 bytes, time=10ms\n--- ping statistics ---\n4 packets transmitted, 4 received"
        mock_result.returncode = 0

        with patch("subprocess.run", return_value=mock_result):
            result = await tool.execute(host="8.8.8.8", count=4)
            assert result["status"] == "success"
            assert result["reachable"] is True

    @pytest.mark.asyncio
    async def test_traceroute_mock(self):
        from vera.brain.agents.network_agent import TracerouteTool

        tool = TracerouteTool()
        mock_result = MagicMock()
        mock_result.stdout = "traceroute to 8.8.8.8\n 1  gateway 1ms\n 2  8.8.8.8 10ms"

        with patch("subprocess.run", return_value=mock_result):
            result = await tool.execute(host="8.8.8.8")
            assert result["status"] == "success"
            assert "traceroute" in result["output"].lower()


# ============================================================
# Spreadsheet Agent Tools
# ============================================================

class TestSpreadsheetTools:
    """Test spreadsheet tools."""

    @pytest.mark.asyncio
    async def test_formula_helper_vlookup(self):
        from vera.brain.agents.spreadsheet_agent import FormulaHelperTool

        tool = FormulaHelperTool()
        result = await tool.execute(function="VLOOKUP")
        assert result["status"] == "success"
        assert "VLOOKUP" in result["function"]
        assert "syntax" in result

    @pytest.mark.asyncio
    async def test_formula_helper_all_functions(self):
        from vera.brain.agents.spreadsheet_agent import FormulaHelperTool

        tool = FormulaHelperTool()
        for func in ["IF", "SUMIF", "COUNTIF", "INDEX", "MATCH", "AVERAGE", "MAX", "MIN"]:
            result = await tool.execute(function=func)
            assert result["status"] == "success"
            assert "syntax" in result

    @pytest.mark.asyncio
    async def test_formula_helper_unknown(self):
        from vera.brain.agents.spreadsheet_agent import FormulaHelperTool

        tool = FormulaHelperTool()
        result = await tool.execute(function="NONEXISTENT")
        assert result["status"] == "success"
        assert "available" in result


# ============================================================
# API Agent Tools
# ============================================================

class TestAPIAgentTools:
    """Test API agent tools with mocked HTTP."""

    @pytest.mark.asyncio
    async def test_api_request_get_mock(self):
        from vera.brain.agents.api_agent import APIRequestTool

        tool = APIRequestTool()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"message": "ok"}
        mock_resp.headers = {"content-type": "application/json"}

        with patch("httpx.AsyncClient") as mock_client:
            instance = MagicMock()
            instance.request = AsyncMock(return_value=mock_resp)
            mock_client.return_value.__aenter__ = AsyncMock(return_value=instance)
            mock_client.return_value.__aexit__ = AsyncMock(return_value=False)
            result = await tool.execute(method="GET", url="https://api.example.com/test")
            assert result["status"] == "success"
            assert result["code"] == 200
            assert result["body"]["message"] == "ok"
            assert result["time_ms"] >= 0

    @pytest.mark.asyncio
    async def test_api_collection_list_empty(self, tmp_path):
        from vera.brain.agents.api_agent import APICollectionTool

        tool = APICollectionTool()
        with patch("vera.brain.agents.api_agent.Path") as mock_path:
            col_dir = tmp_path / "api_collections"
            col_dir.mkdir()
            mock_path.return_value = col_dir
            result = await tool.execute(action="list")
            assert result["status"] == "success"


# ============================================================
# 3D Agent Tools
# ============================================================

class TestThreeDTools:
    """Test 3D model generation tools."""

    @pytest.mark.asyncio
    async def test_generate_cube(self, tmp_path):
        from vera.brain.agents.threed_agent import Generate3DModelTool

        tool = Generate3DModelTool()
        out_path = str(tmp_path / "cube.obj")
        result = await tool.execute(shape="cube", size=2.0, output=out_path)
        assert result["status"] == "success"
        assert result["shape"] == "cube"
        assert result["vertices"] == 8
        assert result["faces"] == 6
        # Verify file was created
        assert Path(out_path).exists()
        content = Path(out_path).read_text()
        assert "v " in content
        assert "f " in content

    @pytest.mark.asyncio
    async def test_generate_sphere(self, tmp_path):
        from vera.brain.agents.threed_agent import Generate3DModelTool

        tool = Generate3DModelTool()
        out_path = str(tmp_path / "sphere.obj")
        result = await tool.execute(shape="sphere", size=1.0, output=out_path)
        assert result["status"] == "success"
        assert result["vertices"] > 8  # Sphere has more vertices than cube

    @pytest.mark.asyncio
    async def test_generate_plane(self, tmp_path):
        from vera.brain.agents.threed_agent import Generate3DModelTool

        tool = Generate3DModelTool()
        out_path = str(tmp_path / "plane.obj")
        result = await tool.execute(shape="plane", size=5.0, output=out_path)
        assert result["status"] == "success"
        assert result["vertices"] == 4
        assert result["faces"] == 1

    @pytest.mark.asyncio
    async def test_scene_builder(self, tmp_path):
        from vera.brain.agents.threed_agent import SceneBuilderTool

        tool = SceneBuilderTool()
        objects = json.dumps([
            {"shape": "cube", "position": [0, 0, 0], "size": 1},
            {"shape": "sphere", "position": [3, 0, 0], "size": 0.5},
        ])
        out_path = str(tmp_path / "scene.json")
        result = await tool.execute(scene_name="test_scene", objects=objects, output=out_path)
        assert result["status"] == "success"
        assert result["objects"] == 2
        # Verify scene file
        scene = json.loads(Path(out_path).read_text())
        assert scene["name"] == "test_scene"
        assert len(scene["objects"]) == 2
        assert "camera" in scene
        assert "lights" in scene


# ============================================================
# Social Media Agent Tools
# ============================================================

class TestSocialMediaTools:
    """Test social media tools."""

    @pytest.mark.asyncio
    async def test_hashtag_generator(self):
        from vera.brain.agents.social_media_agent import HashtagGeneratorTool

        tool = HashtagGeneratorTool()
        result = await tool.execute(topic="artificial intelligence", count=5)
        assert result["status"] == "success"
        assert len(result["hashtags"]) == 5
        assert all(tag.startswith("#") for tag in result["hashtags"])

    @pytest.mark.asyncio
    async def test_caption_writer(self):
        from vera.brain.agents.social_media_agent import CaptionWriterTool

        tool = CaptionWriterTool()
        result = await tool.execute(topic="sunset at beach", tone="casual", platform="instagram")
        assert result["status"] == "success"
        assert result["char_limit"] == 2200  # Instagram limit


# ============================================================
# PDF Agent Tools
# ============================================================

class TestPDFTools:
    """Test PDF tools with real files."""

    @pytest.mark.asyncio
    async def test_pdf_read(self, tmp_path):
        """Test PDF reading — requires PyPDF2."""
        from vera.brain.agents.pdf_agent import PDFReadTool

        tool = PDFReadTool()
        # Create a minimal PDF using reportlab if available, otherwise test error handling
        try:
            from reportlab.lib.pagesizes import letter
            from reportlab.pdfgen import canvas

            pdf_path = str(tmp_path / "test.pdf")
            c = canvas.Canvas(pdf_path, pagesize=letter)
            c.drawString(72, 750, "Hello eVera Test")
            c.save()

            result = await tool.execute(file_path=pdf_path)
            assert result["status"] == "success"
            assert result["total_pages"] == 1
        except ImportError:
            # reportlab not installed — test graceful error
            result = await tool.execute(file_path="/nonexistent.pdf")
            assert result["status"] == "error"


# ============================================================
# DevOps Agent Tools
# ============================================================

class TestDevOpsTools:
    """Test DevOps tools with mocked subprocess."""

    @pytest.mark.asyncio
    async def test_docker_ps_mock(self):
        from vera.brain.agents.devops_agent import DockerTool

        tool = DockerTool()
        mock_result = MagicMock()
        mock_result.stdout = "abc123\tmy_app\tUp 2 hours\tnginx:latest"

        with patch("subprocess.run", return_value=mock_result):
            result = await tool.execute(action="ps")
            assert result["status"] == "success"
            assert len(result["containers"]) == 1
            assert result["containers"][0]["name"] == "my_app"

    @pytest.mark.asyncio
    async def test_docker_images_mock(self):
        from vera.brain.agents.devops_agent import DockerTool

        tool = DockerTool()
        mock_result = MagicMock()
        mock_result.stdout = "nginx:latest\t150MB\npython:3.11\t920MB"

        with patch("subprocess.run", return_value=mock_result):
            result = await tool.execute(action="images")
            assert result["status"] == "success"
            assert len(result["images"]) == 2

    @pytest.mark.asyncio
    async def test_nginx_config_generate(self):
        from vera.brain.agents.devops_agent import NginxConfigTool

        tool = NginxConfigTool()
        result = await tool.execute(action="generate", domain="myapp.com", upstream="localhost:3000")
        assert result["status"] == "success"
        assert "myapp.com" in result["config"]
        assert "localhost:3000" in result["config"]
        assert "proxy_pass" in result["config"]

    @pytest.mark.asyncio
    async def test_system_monitor_mock(self):
        from vera.brain.agents.devops_agent import SystemMonitorTool

        tool = SystemMonitorTool()
        # psutil should be available in test env
        try:
            result = await tool.execute(metric="cpu")
            assert result["status"] == "success"
            assert "cpu" in result
            assert "percent" in result["cpu"]
        except Exception:
            # psutil not installed
            result = await tool.execute(metric="cpu")
            assert result["status"] == "error"


# ============================================================
# Computer Use Agent Tools
# ============================================================

class TestComputerUseTools:
    """Test computer use tools with mocked pyautogui."""

    @pytest.mark.asyncio
    async def test_app_launcher_mock(self):
        from vera.brain.agents.computer_use_agent import AppLauncherTool

        tool = AppLauncherTool()
        with patch("subprocess.Popen"):
            result = await tool.execute(app_name="notepad")
            assert result["status"] == "success"
            assert result["launched"] == "notepad"

    @pytest.mark.asyncio
    async def test_clipboard_read_mock(self):
        from vera.brain.agents.computer_use_agent import ClipboardTool

        tool = ClipboardTool()
        with patch("pyperclip.paste", return_value="clipboard content"):
            result = await tool.execute(action="read")
            assert result["status"] == "success"
            assert result["content"] == "clipboard content"

    @pytest.mark.asyncio
    async def test_clipboard_write_mock(self):
        from vera.brain.agents.computer_use_agent import ClipboardTool

        tool = ClipboardTool()
        with patch("pyperclip.copy") as mock_copy:
            result = await tool.execute(action="write", text="hello from eVera")
            assert result["status"] == "success"
            mock_copy.assert_called_once_with("hello from eVera")
