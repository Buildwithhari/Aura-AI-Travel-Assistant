import os
import unittest
from unittest.mock import patch, MagicMock

import orchestrator
from intent_classifier import CLASSIFIER
from nlu.mbert_classifier import detect_multilingual_text, predict_intent_with_mbert

class TestMbertIntegration(unittest.TestCase):
    def setUp(self):
        # Store original environment variables
        self.orig_use_mbert = os.environ.get("USE_MBERT")
        self.orig_threshold = os.environ.get("MBERT_CONFIDENCE_THRESHOLD")
        
    def tearDown(self):
        # Restore environment variables
        if self.orig_use_mbert is not None:
            os.environ["USE_MBERT"] = self.orig_use_mbert
        elif "USE_MBERT" in os.environ:
            del os.environ["USE_MBERT"]
            
        if self.orig_threshold is not None:
            os.environ["MBERT_CONFIDENCE_THRESHOLD"] = self.orig_threshold
        elif "MBERT_CONFIDENCE_THRESHOLD" in os.environ:
            del os.environ["MBERT_CONFIDENCE_THRESHOLD"]

    def test_1_use_mbert_false_runs_normally(self):
        """1. USE_MBERT=false -> app runs normally"""
        os.environ["USE_MBERT"] = "false"
        state = orchestrator.new_state("test-session")
        state = orchestrator.run_turn(state, "hello")
        
        self.assertEqual(state["intent"], "greeting")
        self.assertEqual(state["_last"]["source"], "fast")

    def test_2_english_normal_query_works_without_mbert(self):
        """2. English normal query should work without mBERT"""
        os.environ["USE_MBERT"] = "false"
        state = orchestrator.new_state("test-session")
        state = orchestrator.run_turn(state, "book a flight")
        
        self.assertEqual(state["intent"], "flight_search")
        self.assertEqual(state["_last"]["source"], "fast")

    @patch("nlu.mbert_classifier.predict_intent_with_mbert")
    def test_3_low_confidence_mixed_language_calls_mbert_if_enabled(self, mock_predict):
        """3. Low-confidence mixed-language query should call mBERT if enabled"""
        os.environ["USE_MBERT"] = "true"
        os.environ["MBERT_CONFIDENCE_THRESHOLD"] = "0.70"
        
        # Setup mock to return flight_search with good confidence
        mock_predict.return_value = {
            "intent": "flight_search",
            "confidence": 0.85,
            "source": "mbert"
        }
        
        state = orchestrator.new_state("test-session")
        # Mixed language text that is not clearly in custom training set
        state = orchestrator.run_turn(state, "naan Bangalore to Mumbai poganum")
        
        self.assertTrue(mock_predict.called)
        self.assertEqual(state["intent"], "flight_search")
        self.assertEqual(state["_last"]["source"], "mbert")

    @patch("nlu.mbert_classifier.predict_intent_with_mbert")
    def test_4_chennai_la_irundhu_delhi_ku_flight_venum_intent_flight_search(self, mock_predict):
        """4. 'Chennai la irundhu Delhi ku flight venum' -> intent = flight_search"""
        os.environ["USE_MBERT"] = "true"
        os.environ["MBERT_CONFIDENCE_THRESHOLD"] = "0.70"
        
        mock_predict.return_value = {
            "intent": "flight_search",
            "confidence": 0.82,
            "source": "mbert"
        }
        
        state = orchestrator.new_state("test-session")
        state = orchestrator.run_turn(state, "Chennai la irundhu Delhi ku flight venum")
        
        self.assertEqual(state["intent"], "flight_search")
        self.assertEqual(state["_last"]["source"], "mbert")
        # Verify custom entity extraction still extracted city entities
        self.assertEqual(state["slots"]["origin"], "Chennai")
        self.assertEqual(state["slots"]["destination"], "Delhi")

    @patch("nlu.mbert_classifier.predict_intent_with_mbert")
    def test_5_goa_la_hotel_venum_intent_hotel_search(self, mock_predict):
        """5. 'Goa la hotel venum' -> intent = hotel_search"""
        os.environ["USE_MBERT"] = "true"
        os.environ["MBERT_CONFIDENCE_THRESHOLD"] = "0.70"
        
        mock_predict.return_value = {
            "intent": "hotel_search",
            "confidence": 0.88,
            "source": "mbert"
        }
        
        state = orchestrator.new_state("test-session")
        state = orchestrator.run_turn(state, "Goa la hotel venum")
        
        self.assertEqual(state["intent"], "hotel_search")
        self.assertEqual(state["_last"]["source"], "mbert")
        self.assertEqual(state["slots"]["destination"], "Goa")

    @patch("nlu.mbert_classifier.predict_intent_with_mbert")
    def test_6_mbert_failure_does_not_crash_app(self, mock_predict):
        """6. mBERT failure should not crash app (fallback to custom fallback reply)"""
        os.environ["USE_MBERT"] = "true"
        # Mocking an exception being raised during prediction
        mock_predict.side_effect = RuntimeError("Transformers not working")
        
        state = orchestrator.new_state("test-session")
        try:
            state = orchestrator.run_turn(state, "some extremely random query containing venum")
            # Should fallback to custom_fallback source and fallback intent
            self.assertEqual(state["intent"], "fallback")
            self.assertEqual(state["_last"]["source"], "custom_fallback")
            self.assertIn("rephrase", state["_last"]["reply"].lower())
        except Exception as e:
            self.fail(f"App crashed on mBERT failure with exception: {e}")

    def test_7_existing_seat_selection_flow_does_not_break(self):
        """7. Existing seat selection flow should not break"""
        state = orchestrator.new_state("test-seat")
        state["current_flow"] = "seat_selection"
        state["booking_stage"] = "seat_selection"
        
        # Test that user query resets flight/seat if booking is complete
        state = orchestrator.run_turn(state, "new search")
        self.assertIsNone(state.get("selected_flight"))
        self.assertIsNone(state.get("selected_seat"))

    def test_8_existing_multi_city_flow_does_not_break(self):
        """8. Multi-city parsing still works (dates are now relative so they never fall in the past)."""
        from datetime import timedelta
        import dates as D
        d1 = (D.today_for() + timedelta(days=20)).isoformat()
        d2 = (D.today_for() + timedelta(days=25)).isoformat()
        state = orchestrator.new_state("test-multi-city")
        state = orchestrator.run_turn(state, f"BLR to DEL on {d1} and DEL to BOM on {d2} for 2 adults economy")
        p = state["_last"]
        self.assertEqual(p["slots"]["trip_type"], "multi_city")
        self.assertEqual(len(p["slots"]["segments"]), 2)
        self.assertEqual(p["slots"]["segments"][0]["origin"], "Bengaluru")
        self.assertEqual(p["slots"]["segments"][1]["destination"], "Mumbai")

    def test_9_existing_voice_assistant_does_not_break(self):
        """9. Existing voice assistant should not break"""
        state = orchestrator.new_state("test-voice")
        state = orchestrator.run_turn(state, "hello")
        p = state["_last"]
        
        # Voice assistant relies on having a clear string reply to speak out loud
        self.assertIn("reply", p)
        self.assertIsInstance(p["reply"], str)
        self.assertTrue(len(p["reply"]) > 0)

    def test_detect_multilingual_text(self):
        """Verify detect_multilingual_text correctly recognizes Hindi, Tamil, Kannada, and Telugu indicators"""
        # Hindi transliterated
        self.assertTrue(detect_multilingual_text("Delhi ke liye flight chahiye"))
        # Tamil transliterated
        self.assertTrue(detect_multilingual_text("Chennai la irundhu flight venum"))
        # Kannada transliterated
        self.assertTrue(detect_multilingual_text("Bengaluru inda flight beku"))
        # Telugu transliterated
        self.assertTrue(detect_multilingual_text("Hyderabad nundi flight kavali"))
        # Non-multilingual English
        is_multi = detect_multilingual_text("book a flight from Delhi to Mumbai")
        self.assertFalse(is_multi)
        # Unicode Tamil
        self.assertTrue(detect_multilingual_text("சென்னை"))
        # Unicode Hindi
        self.assertTrue(detect_multilingual_text("उड़ान"))

if __name__ == "__main__":
    unittest.main()
