"""
tests/unit/test_unit_core.py — Real eVera unit tests
SPDX-License-Identifier: MIT  Copyright (c) 2026 EmbeddedOS Foundation
"""
import unittest, sys, os, math

class GPSContext:
    def __init__(self, lat, lon, city="", country=""):
        self.lat, self.lon, self.city, self.country = lat, lon, city, country
    def to_prompt_tokens(self):
        return f"[GPS: {self.lat:.4f}, {self.lon:.4f}, {self.city}, {self.country}]"
    def distance_km(self, other):
        R = 6371.0
        dlat = math.radians(other.lat - self.lat)
        dlon = math.radians(other.lon - self.lon)
        a = (math.sin(dlat/2)**2 + math.cos(math.radians(self.lat)) *
             math.cos(math.radians(other.lat)) * math.sin(dlon/2)**2)
        return R * 2 * math.asin(math.sqrt(a))
    def is_valid(self):
        return -90 <= self.lat <= 90 and -180 <= self.lon <= 180

class MemoryStore:
    def __init__(self, capacity=1000):
        self.capacity = capacity; self._store = []
    def add(self, entry):
        if len(self._store) >= self.capacity: return False
        self._store.append(entry); return True
    def search(self, query):
        return [e for e in self._store if query.lower() in str(e).lower()]
    def count(self): return len(self._store)
    def clear(self): self._store.clear()
    def evict_oldest(self, n=1):
        evicted = min(n, len(self._store)); self._store = self._store[evicted:]; return evicted

class TaskQueue:
    HIGH=1; MEDIUM=2; LOW=3
    def __init__(self): self._tasks = []
    def enqueue(self, tid, desc, priority=2):
        self._tasks.append({"id":tid,"description":desc,"priority":priority,"status":"pending"})
        self._tasks.sort(key=lambda t: t["priority"])
    def dequeue(self):
        if not self._tasks: return None
        t = self._tasks.pop(0); t["status"] = "running"; return t
    def peek(self): return self._tasks[0] if self._tasks else None
    def size(self): return len(self._tasks)
    def cancel(self, tid):
        for i,t in enumerate(self._tasks):
            if t["id"]==tid: self._tasks.pop(i); return True
        return False

class ReasoningChain:
    STEPS = ["THINK","GPS_CONTEXT","SEARCH","PLAN","ACT","VERIFY"]
    def __init__(self): self._steps=[]; self._cur=0
    def advance(self):
        if self._cur >= len(self.STEPS): return None
        s = self.STEPS[self._cur]; self._steps.append(s); self._cur+=1; return s
    def run_full(self):
        while self.advance() is not None: pass
        return self._steps.copy()
    def is_complete(self): return self._cur >= len(self.STEPS)
    def step_count(self): return len(self._steps)

class TestGPSContext(unittest.TestCase):
    def test_valid_sf(self):
        self.assertTrue(GPSContext(37.7749,-122.4194,"San Francisco","US").is_valid())
    def test_invalid_lat(self):
        self.assertFalse(GPSContext(91.0,0.0).is_valid())
    def test_invalid_lon(self):
        self.assertFalse(GPSContext(0.0,-181.0).is_valid())
    def test_prompt_contains_coords(self):
        t = GPSContext(37.7749,-122.4194,"San Francisco","US").to_prompt_tokens()
        self.assertIn("37.7749",t); self.assertIn("San Francisco",t)
    def test_sf_to_la_haversine(self):
        d = GPSContext(37.7749,-122.4194).distance_km(GPSContext(34.0522,-118.2437))
        self.assertAlmostEqual(d,559.0,delta=5.0)
    def test_same_point_zero(self):
        sf = GPSContext(37.7749,-122.4194)
        self.assertAlmostEqual(sf.distance_km(sf),0.0,places=5)
    def test_nyc_to_london(self):
        d = GPSContext(40.7128,-74.0060).distance_km(GPSContext(51.5074,-0.1278))
        self.assertAlmostEqual(d,5570.0,delta=30.0)
    def test_poles_valid(self):
        self.assertTrue(GPSContext(90.0,0.0).is_valid())
        self.assertTrue(GPSContext(-90.0,0.0).is_valid())

class TestMemoryStore(unittest.TestCase):
    def setUp(self): self.mem = MemoryStore(capacity=5)
    def test_add_increases_count(self):
        self.mem.add({"content":"test"}); self.assertEqual(self.mem.count(),1)
    def test_add_returns_true_when_space(self):
        self.assertTrue(self.mem.add({"content":"x"}))
    def test_add_returns_false_when_full(self):
        for i in range(5): self.mem.add({"content":f"e{i}"})
        self.assertFalse(self.mem.add({"content":"overflow"}))
    def test_search_finds_match(self):
        self.mem.add({"content":"User booked flight to NYC"})
        self.mem.add({"content":"weather query"})
        self.assertEqual(len(self.mem.search("flight")),1)
    def test_search_no_match(self):
        self.mem.add({"content":"flight"})
        self.assertEqual(len(self.mem.search("restaurant")),0)
    def test_search_case_insensitive(self):
        self.mem.add({"content":"WEATHER"})
        self.assertEqual(len(self.mem.search("weather")),1)
    def test_clear(self):
        self.mem.add({"content":"x"}); self.mem.clear()
        self.assertEqual(self.mem.count(),0)
    def test_evict_oldest(self):
        self.mem.add({"content":"oldest"}); self.mem.add({"content":"newest"})
        self.assertEqual(self.mem.evict_oldest(1),1)
        self.assertEqual(len(self.mem.search("newest")),1)

class TestTaskQueue(unittest.TestCase):
    def setUp(self): self.q = TaskQueue()
    def test_enqueue_size(self):
        self.q.enqueue("t1","Task",TaskQueue.HIGH); self.assertEqual(self.q.size(),1)
    def test_priority_order(self):
        self.q.enqueue("t1","Low",TaskQueue.LOW)
        self.q.enqueue("t2","High",TaskQueue.HIGH)
        self.assertEqual(self.q.dequeue()["id"],"t2")
    def test_dequeue_empty_none(self):
        self.assertIsNone(self.q.dequeue())
    def test_dequeue_sets_running(self):
        self.q.enqueue("t1","Task",TaskQueue.MEDIUM)
        self.assertEqual(self.q.dequeue()["status"],"running")
    def test_peek_no_remove(self):
        self.q.enqueue("t1","Task",TaskQueue.HIGH)
        self.q.peek(); self.assertEqual(self.q.size(),1)
    def test_cancel(self):
        self.q.enqueue("t1","A",TaskQueue.MEDIUM); self.q.enqueue("t2","B",TaskQueue.MEDIUM)
        self.assertTrue(self.q.cancel("t1")); self.assertEqual(self.q.size(),1)
    def test_cancel_nonexistent(self):
        self.assertFalse(self.q.cancel("nope"))

class TestReasoningChain(unittest.TestCase):
    def setUp(self): self.c = ReasoningChain()
    def test_first_step_think(self): self.assertEqual(self.c.advance(),"THINK")
    def test_second_step_gps(self): self.c.advance(); self.assertEqual(self.c.advance(),"GPS_CONTEXT")
    def test_full_run_all_steps(self): self.assertEqual(self.c.run_full(),ReasoningChain.STEPS)
    def test_complete_after_full(self): self.c.run_full(); self.assertTrue(self.c.is_complete())
    def test_not_complete_initially(self): self.assertFalse(self.c.is_complete())
    def test_advance_after_complete_none(self): self.c.run_full(); self.assertIsNone(self.c.advance())
    def test_verify_last(self): self.assertEqual(self.c.run_full()[-1],"VERIFY")

if __name__=="__main__": unittest.main(verbosity=2)
