# -*- coding: utf-8 -*-
"""
Reply-language catalogue for Aura (English, Kannada, Hindi).

* `t(key, lang, **values)` fills placeholders. Values (dates, prices, codes,
  names, numbers) are inserted verbatim so they are never mistranslated.
* English entries may be a (singular, plural) tuple chosen by `n`.
* `UI` holds the labels the browser uses on cards and controls, so a Kannada
  journey stays Kannada on the cards too.
* tests/test_i18n.py checks every key exists in every language with the same
  placeholders.
"""

from __future__ import annotations

import re

LANGS = {"en": "English", "kn": "ಕನ್ನಡ", "hi": "हिन्दी"}

M: dict[str, dict] = {
    # ---------------- general
    "welcome": {"en": "Hi, I'm Aura. Where would you like to go?",
                "kn": "ನಮಸ್ಕಾರ, ನಾನು ಔರಾ. ನೀವು ಎಲ್ಲಿಗೆ ಹೋಗಲು ಬಯಸುತ್ತೀರಿ?",
                "hi": "नमस्ते, मैं ऑरा हूँ। आप कहाँ जाना चाहेंगे?"},
    "greeting": {"en": "Hi! I can find sample flights and hotels, or plan a trip. What are you planning?",
                 "kn": "ನಮಸ್ಕಾರ! ನಾನು ಮಾದರಿ ವಿಮಾನಗಳು ಮತ್ತು ಹೋಟೆಲ್‌ಗಳನ್ನು ಹುಡುಕಬಲ್ಲೆ ಅಥವಾ ಪ್ರವಾಸ ಯೋಜಿಸಬಲ್ಲೆ. ನೀವು ಏನು ಯೋಜಿಸುತ್ತಿದ್ದೀರಿ?",
                 "hi": "नमस्ते! मैं सैंपल फ़्लाइट और होटल ढूँढ सकती हूँ, या यात्रा की योजना बना सकती हूँ। आप क्या प्लान कर रहे हैं?"},
    "how_are_you": {"en": "I'm doing well, thanks! Where are you headed?",
                    "kn": "ನಾನು ಚೆನ್ನಾಗಿದ್ದೇನೆ, ಧನ್ಯವಾದಗಳು! ನೀವು ಎಲ್ಲಿಗೆ ಹೊರಟಿದ್ದೀರಿ?",
                    "hi": "मैं ठीक हूँ, धन्यवाद! आप कहाँ जा रहे हैं?"},
    "who_are_you": {"en": "I'm Aura, a travel assistant. I can help with sample flights, hotels and trip plans.",
                    "kn": "ನಾನು ಔರಾ, ಪ್ರಯಾಣ ಸಹಾಯಕಿ. ಮಾದರಿ ವಿಮಾನಗಳು, ಹೋಟೆಲ್‌ಗಳು ಮತ್ತು ಪ್ರವಾಸ ಯೋಜನೆಗಳಿಗೆ ಸಹಾಯ ಮಾಡಬಲ್ಲೆ.",
                    "hi": "मैं ऑरा हूँ, एक ट्रैवल असिस्टेंट। मैं सैंपल फ़्लाइट, होटल और यात्रा योजनाओं में मदद कर सकती हूँ।"},
    "help": {"en": "You can tell me your plans in your own words, for example “Bengaluru to Delhi next Friday for 2”, “hotel in Goa for 3 nights” or “plan a 5-day Kerala trip”. I can also answer questions about baggage, visas and check-in.",
             "kn": "ನಿಮ್ಮ ಯೋಜನೆಯನ್ನು ನಿಮ್ಮದೇ ಮಾತಿನಲ್ಲಿ ಹೇಳಿ, ಉದಾಹರಣೆಗೆ “ಮುಂದಿನ ಶುಕ್ರವಾರ ಬೆಂಗಳೂರಿನಿಂದ ದೆಹಲಿಗೆ ಇಬ್ಬರು”, “ಗೋವಾದಲ್ಲಿ 3 ರಾತ್ರಿ ಹೋಟೆಲ್” ಅಥವಾ “5 ದಿನದ ಕೇರಳ ಪ್ರವಾಸ ಯೋಜಿಸಿ”. ಬ್ಯಾಗೇಜ್, ವೀಸಾ ಮತ್ತು ಚೆಕ್-ಇನ್ ಕುರಿತು ಪ್ರಶ್ನೆಗಳಿಗೂ ಉತ್ತರಿಸಬಲ್ಲೆ.",
             "hi": "अपनी योजना अपने शब्दों में बताइए, जैसे “अगले शुक्रवार बेंगलुरु से दिल्ली, 2 लोग”, “गोवा में 3 रात के लिए होटल” या “5 दिन की केरल यात्रा प्लान करो”। मैं बैगेज, वीज़ा और चेक-इन के सवालों का भी जवाब दे सकती हूँ।"},
    "goodbye": {"en": "Safe travels! Come back any time.", "kn": "ಶುಭ ಪ್ರಯಾಣ! ಯಾವಾಗ ಬೇಕಾದರೂ ಮರಳಿ ಬನ್ನಿ.",
                "hi": "सुरक्षित यात्रा! कभी भी वापस आइए।"},
    "handoff": {"en": "I'll pass this conversation to a human travel agent so you won't have to repeat yourself. (In this demo no agent is connected.)",
                "kn": "ಈ ಸಂಭಾಷಣೆಯನ್ನು ಮಾನವ ಟ್ರಾವೆಲ್ ಏಜೆಂಟ್‌ಗೆ ಹಸ್ತಾಂತರಿಸುತ್ತೇನೆ, ನೀವು ಮತ್ತೆ ಹೇಳಬೇಕಾಗಿಲ್ಲ. (ಈ ಡೆಮೊದಲ್ಲಿ ಯಾವುದೇ ಏಜೆಂಟ್ ಸಂಪರ್ಕದಲ್ಲಿಲ್ಲ.)",
                "hi": "मैं यह बातचीत एक ट्रैवल एजेंट को सौंप दूँगी ताकि आपको दोबारा न बताना पड़े। (इस डेमो में कोई एजेंट जुड़ा नहीं है।)"},
    "reset": {"en": "Okay, starting fresh. Where would you like to go?", "kn": "ಸರಿ, ಹೊಸದಾಗಿ ಪ್ರಾರಂಭಿಸೋಣ. ನೀವು ಎಲ್ಲಿಗೆ ಹೋಗಲು ಬಯಸುತ್ತೀರಿ?",
              "hi": "ठीक है, नए सिरे से शुरू करते हैं। आप कहाँ जाना चाहेंगे?"},
    "language_set": {"en": "Okay, I'll reply in English from now on.", "kn": "ಸರಿ, ಇನ್ನು ಮುಂದೆ ಕನ್ನಡದಲ್ಲಿ ಉತ್ತರಿಸುತ್ತೇನೆ.",
                     "hi": "ठीक है, अब से मैं हिन्दी में जवाब दूँगी।"},
    "clarify": {"en": "Sorry, I'm not sure what you mean. I can search sample flights or hotels, plan a trip, or answer travel questions like baggage rules.",
                "kn": "ಕ್ಷಮಿಸಿ, ನಿಮ್ಮ ಅರ್ಥ ನನಗೆ ಸ್ಪಷ್ಟವಾಗಲಿಲ್ಲ. ನಾನು ಮಾದರಿ ವಿಮಾನ ಅಥವಾ ಹೋಟೆಲ್ ಹುಡುಕಬಲ್ಲೆ, ಪ್ರವಾಸ ಯೋಜಿಸಬಲ್ಲೆ ಅಥವಾ ಬ್ಯಾಗೇಜ್ ನಿಯಮಗಳಂತಹ ಪ್ರಶ್ನೆಗಳಿಗೆ ಉತ್ತರಿಸಬಲ್ಲೆ.",
                "hi": "माफ़ कीजिए, मैं समझ नहीं पाई। मैं सैंपल फ़्लाइट या होटल ढूँढ सकती हूँ, यात्रा प्लान कर सकती हूँ, या बैगेज नियम जैसे सवालों के जवाब दे सकती हूँ।"},
    "clarify_rephrase": {"en": "I couldn't understand that reliably. Could you rephrase it? For example: “Flight from Bengaluru to Delhi on 10 Oct”.",
                         "kn": "ಅದನ್ನು ನಾನು ನಿಖರವಾಗಿ ಅರ್ಥಮಾಡಿಕೊಳ್ಳಲಾಗಲಿಲ್ಲ. ದಯವಿಟ್ಟು ಬೇರೆ ರೀತಿಯಲ್ಲಿ ಹೇಳುವಿರಾ? ಉದಾಹರಣೆ: “10 ಅಕ್ಟೋಬರ್ ಬೆಂಗಳೂರಿನಿಂದ ದೆಹಲಿಗೆ ವಿಮಾನ”.",
                         "hi": "मैं इसे ठीक से समझ नहीं पाई। क्या आप दूसरे शब्दों में बता सकते हैं? उदाहरण: “10 अक्टूबर को बेंगलुरु से दिल्ली की फ़्लाइट”।"},
    "didnt_get": {"en": "Sorry, I didn't catch that.", "kn": "ಕ್ಷಮಿಸಿ, ಅದು ನನಗೆ ಅರ್ಥವಾಗಲಿಲ್ಲ.", "hi": "माफ़ कीजिए, मैं समझ नहीं पाई।"},
    "domain_fallback": {"en": "I don't have reliable information on that. I can help with flights, hotels, trip plans and travel rules such as baggage, visas and check-in.",
                        "kn": "ಅದರ ಬಗ್ಗೆ ನನ್ನಲ್ಲಿ ವಿಶ್ವಾಸಾರ್ಹ ಮಾಹಿತಿ ಇಲ್ಲ. ವಿಮಾನ, ಹೋಟೆಲ್, ಪ್ರವಾಸ ಯೋಜನೆ ಮತ್ತು ಬ್ಯಾಗೇಜ್, ವೀಸಾ, ಚೆಕ್-ಇನ್ ನಿಯಮಗಳಿಗೆ ಸಹಾಯ ಮಾಡಬಲ್ಲೆ.",
                        "hi": "इस बारे में मेरे पास भरोसेमंद जानकारी नहीं है। मैं फ़्लाइट, होटल, यात्रा योजना और बैगेज, वीज़ा, चेक-इन नियमों में मदद कर सकती हूँ।"},
    "english_only": {"en": "", "kn": "(ಈ ಮಾಹಿತಿ ಸದ್ಯಕ್ಕೆ ಇಂಗ್ಲಿಷ್‌ನಲ್ಲಿ ಮಾತ್ರ ಲಭ್ಯವಿದೆ.)", "hi": "(यह जानकारी अभी केवल अंग्रेज़ी में उपलब्ध है।)"},
    "visa_domestic": {"en": "You don't need a visa to travel within India; visa rules only apply to international trips. Carry a valid photo ID for domestic flights.",
                      "kn": "ಭಾರತದೊಳಗೆ ಪ್ರಯಾಣಿಸಲು ವೀಸಾ ಬೇಕಾಗಿಲ್ಲ; ವೀಸಾ ನಿಯಮಗಳು ಅಂತರರಾಷ್ಟ್ರೀಯ ಪ್ರಯಾಣಕ್ಕೆ ಮಾತ್ರ. ದೇಶೀಯ ವಿಮಾನಗಳಿಗೆ ಮಾನ್ಯ ಫೋಟೋ ಗುರುತಿನ ಚೀಟಿ ಒಯ್ಯಿರಿ.",
                      "hi": "भारत के अंदर यात्रा के लिए वीज़ा की ज़रूरत नहीं है; वीज़ा नियम केवल अंतरराष्ट्रीय यात्रा पर लागू होते हैं। घरेलू उड़ानों के लिए वैध फ़ोटो पहचान पत्र साथ रखें।"},
    "what_for": {"en": "What would you like for {place}: flights, a hotel or a trip plan?",
                 "kn": "{place} ಗಾಗಿ ನಿಮಗೆ ಏನು ಬೇಕು: ವಿಮಾನ, ಹೋಟೆಲ್ ಅಥವಾ ಪ್ರವಾಸ ಯೋಜನೆ?",
                 "hi": "{place} के लिए आपको क्या चाहिए: फ़्लाइट, होटल या यात्रा योजना?"},
    "ack": {"en": "Got it: {items}.", "kn": "ಸರಿ: {items}.", "hi": "ठीक है: {items}।"},

    # ---------------- flight acks
    "ack_origin": {"en": "from {place}", "kn": "{place} ನಿಂದ", "hi": "{place} से"},
    "ack_destination": {"en": "to {place}", "kn": "{place} ಗೆ", "hi": "{place} तक"},
    "ack_leg": {"en": "flight {n}: {details}", "kn": "ವಿಮಾನ {n}: {details}", "hi": "फ़्लाइट {n}: {details}"},
    "note_return_cleared": {"en": "The new departure is on or after your return date, so I've cleared the return date.",
                            "kn": "ಹೊಸ ಹೊರಡುವ ದಿನಾಂಕ ಹಿಂತಿರುಗುವ ದಿನಾಂಕದಂದು ಅಥವಾ ನಂತರ ಇದೆ, ಆದ್ದರಿಂದ ಹಿಂತಿರುಗುವ ದಿನಾಂಕ ತೆಗೆದಿದ್ದೇನೆ.",
                            "hi": "नई प्रस्थान तारीख वापसी की तारीख पर या उसके बाद है, इसलिए वापसी की तारीख हटा दी है।"},
    "ack_depart": {"en": "departing {date}", "kn": "ಹೊರಡುವುದು {date}", "hi": "प्रस्थान {date}"},
    "ack_return": {"en": "returning {date}", "kn": "ಹಿಂತಿರುಗುವುದು {date}", "hi": "वापसी {date}"},
    "ack_cabin": {"en": "{cabin}", "kn": "{cabin}", "hi": "{cabin}"},
    "ack_trip_one_way": {"en": "one-way", "kn": "ಒನ್-ವೇ", "hi": "वन-वे"},
    "ack_trip_round_trip": {"en": "round-trip", "kn": "ರೌಂಡ್-ಟ್ರಿಪ್", "hi": "राउंड-ट्रिप"},
    "ack_trip_multi_city": {"en": "multi-city", "kn": "ಮಲ್ಟಿ-ಸಿಟಿ", "hi": "मल्टी-सिटी"},
    "note_return_removed": {"en": "I've removed the return date.", "kn": "ಹಿಂತಿರುಗುವ ದಿನಾಂಕವನ್ನು ತೆಗೆದುಹಾಕಿದ್ದೇನೆ.", "hi": "मैंने वापसी की तारीख हटा दी है।"},
    "note_switched_round": {"en": "Since you mentioned a return, I've made this a round trip.",
                            "kn": "ನೀವು ಹಿಂತಿರುಗುವುದನ್ನು ಹೇಳಿದ್ದರಿಂದ ಇದನ್ನು ರೌಂಡ್-ಟ್ರಿಪ್ ಮಾಡಿದ್ದೇನೆ.",
                            "hi": "आपने वापसी बताई, इसलिए मैंने इसे राउंड-ट्रिप कर दिया है।"},

    # ---------------- flight questions
    "ask_trip_type": {"en": "Sure. Is it one-way, round-trip or multi-city?",
                      "kn": "ಸರಿ. ಇದು ಒನ್-ವೇ, ರೌಂಡ್-ಟ್ರಿಪ್ ಅಥವಾ ಮಲ್ಟಿ-ಸಿಟಿ?",
                      "hi": "ज़रूर। यह वन-वे है, राउंड-ट्रिप या मल्टी-सिटी?"},
    "ask_trip_type_route": {"en": "{route}: one-way, round-trip or multi-city?",
                            "kn": "{route}: ಒನ್-ವೇ, ರೌಂಡ್-ಟ್ರಿಪ್ ಅಥವಾ ಮಲ್ಟಿ-ಸಿಟಿ?",
                            "hi": "{route}: वन-वे, राउंड-ट्रिप या मल्टी-सिटी?"},
    "ask_origin": {"en": "Where are you flying from?", "kn": "ನೀವು ಎಲ್ಲಿಂದ ಹೊರಡುತ್ತೀರಿ?", "hi": "आप कहाँ से उड़ान भरेंगे?"},
    "ask_origin_dest": {"en": "Where are you flying to {dest} from?", "kn": "{dest} ಗೆ ನೀವು ಎಲ್ಲಿಂದ ಹೊರಡುತ್ತೀರಿ?",
                        "hi": "{dest} के लिए आप कहाँ से उड़ान भरेंगे?"},
    "ask_destination": {"en": "Where would you like to fly to?", "kn": "ನೀವು ಎಲ್ಲಿಗೆ ಹೋಗಲು ಬಯಸುತ್ತೀರಿ?", "hi": "आप कहाँ जाना चाहेंगे?"},
    "ask_destination_from": {"en": "Where are you flying to from {origin}?", "kn": "{origin} ನಿಂದ ನೀವು ಎಲ್ಲಿಗೆ ಹೋಗುತ್ತೀರಿ?",
                             "hi": "{origin} से आप कहाँ जाएँगे?"},
    "ask_role": {"en": "Is {place} where you're flying from, or where you're going?",
                 "kn": "{place} ನೀವು ಹೊರಡುವ ಸ್ಥಳವೇ ಅಥವಾ ಹೋಗುವ ಸ್ಥಳವೇ?",
                 "hi": "{place} वह जगह है जहाँ से आप उड़ेंगे या जहाँ जा रहे हैं?"},
    "ask_depart": {"en": "When do you want to fly {route}?", "kn": "{route} ಯಾವ ದಿನ ಪ್ರಯಾಣಿಸಲು ಬಯಸುತ್ತೀರಿ?",
                   "hi": "{route} आप किस दिन उड़ना चाहेंगे?"},
    "ask_return": {"en": "And when do you want to come back? It has to be after {date}.",
                   "kn": "ಮತ್ತು ನೀವು ಯಾವಾಗ ಹಿಂತಿರುಗುತ್ತೀರಿ? ಅದು {date} ನಂತರ ಇರಬೇಕು.",
                   "hi": "और आप कब वापस आना चाहेंगे? यह {date} के बाद होनी चाहिए।"},
    "ask_pax_cabin": {"en": "How many people are travelling, and which cabin: Economy, Premium Economy, Business or First?",
                      "kn": "ಎಷ್ಟು ಜನ ಪ್ರಯಾಣಿಸುತ್ತಿದ್ದಾರೆ, ಮತ್ತು ಯಾವ ಕ್ಯಾಬಿನ್: ಎಕಾನಮಿ, ಪ್ರೀಮಿಯಂ ಎಕಾನಮಿ, ಬಿಸಿನೆಸ್ ಅಥವಾ ಫಸ್ಟ್?",
                      "hi": "कितने लोग यात्रा कर रहे हैं, और कौन-सा केबिन: इकॉनमी, प्रीमियम इकॉनमी, बिज़नेस या फ़र्स्ट?"},
    "ask_pax": {"en": "How many people are travelling? For example “2 adults and 1 child”.",
                "kn": "ಎಷ್ಟು ಜನ ಪ್ರಯಾಣಿಸುತ್ತಿದ್ದಾರೆ? ಉದಾಹರಣೆಗೆ “2 ವಯಸ್ಕರು ಮತ್ತು 1 ಮಗು”.",
                "hi": "कितने लोग यात्रा कर रहे हैं? जैसे “2 वयस्क और 1 बच्चा”।"},
    "ask_cabin": {"en": "Which cabin would you like: Economy, Premium Economy, Business or First?",
                  "kn": "ಯಾವ ಕ್ಯಾಬಿನ್ ಬೇಕು: ಎಕಾನಮಿ, ಪ್ರೀಮಿಯಂ ಎಕಾನಮಿ, ಬಿಸಿನೆಸ್ ಅಥವಾ ಫಸ್ಟ್?",
                  "hi": "कौन-सा केबिन चाहिए: इकॉनमी, प्रीमियम इकॉनमी, बिज़नेस या फ़र्स्ट?"},
    "ask_family": {"en": "{n} travellers. How many are adults, children (2–11) and infants (under 2)?",
                   "kn": "{n} ಪ್ರಯಾಣಿಕರು. ಅವರಲ್ಲಿ ಎಷ್ಟು ವಯಸ್ಕರು, ಮಕ್ಕಳು (2–11) ಮತ್ತು ಶಿಶುಗಳು (2 ವರ್ಷದೊಳಗೆ)?",
                   "hi": "{n} यात्री। इनमें कितने वयस्क, बच्चे (2–11) और शिशु (2 साल से कम) हैं?"},
    "ask_date_which": {"en": "Should {date} be the departure date or the return date?",
                       "kn": "{date} ಹೊರಡುವ ದಿನಾಂಕವೇ ಅಥವಾ ಹಿಂತಿರುಗುವ ದಿನಾಂಕವೇ?",
                       "hi": "{date} प्रस्थान की तारीख है या वापसी की?"},
    "ask_airport_choice": {"en": "{place} has more than one airport. Which one should I use?",
                           "kn": "{place} ನಲ್ಲಿ ಒಂದಕ್ಕಿಂತ ಹೆಚ್ಚು ವಿಮಾನ ನಿಲ್ದಾಣಗಳಿವೆ. ಯಾವುದನ್ನು ಬಳಸಲಿ?",
                           "hi": "{place} में एक से ज़्यादा हवाई अड्डे हैं। कौन-सा इस्तेमाल करूँ?"},
    "ask_state_airport": {"en": "{place} is a state, not a single airport. Which airport should I use?",
                          "kn": "{place} ಒಂದು ರಾಜ್ಯ, ಒಂದೇ ವಿಮಾನ ನಿಲ್ದಾಣವಲ್ಲ. ಯಾವ ವಿಮಾನ ನಿಲ್ದಾಣ ಬಳಸಲಿ?",
                          "hi": "{place} एक राज्य है, एक हवाई अड्डा नहीं। कौन-सा हवाई अड्डा इस्तेमाल करूँ?"},
    "ask_state_gateway": {"en": "{place} has no major airport in my list. Travellers usually fly into one of these. Which one?",
                          "kn": "ನನ್ನ ಪಟ್ಟಿಯಲ್ಲಿ {place} ಗೆ ಪ್ರಮುಖ ವಿಮಾನ ನಿಲ್ದಾಣವಿಲ್ಲ. ಪ್ರಯಾಣಿಕರು ಸಾಮಾನ್ಯವಾಗಿ ಇವುಗಳಲ್ಲಿ ಒಂದಕ್ಕೆ ಬರುತ್ತಾರೆ. ಯಾವುದು?",
                          "hi": "मेरी सूची में {place} का कोई बड़ा हवाई अड्डा नहीं है। यात्री आमतौर पर इनमें से किसी एक पर आते हैं। कौन-सा?"},
    "ask_country_airport": {"en": "Which airport in {place}?", "kn": "{place} ನಲ್ಲಿ ಯಾವ ವಿಮಾನ ನಿಲ್ದಾಣ?", "hi": "{place} में कौन-सा हवाई अड्डा?"},
    "ask_city_in_country": {"en": "Which city in {place}?", "kn": "{place} ನ ಯಾವ ನಗರ?", "hi": "{place} का कौन-सा शहर?"},
    "did_you_mean": {"en": "I couldn't find “{place}”. Did you mean one of these?",
                     "kn": "“{place}” ಸಿಗಲಿಲ್ಲ. ನೀವು ಇವುಗಳಲ್ಲಿ ಒಂದನ್ನು ಅರ್ಥೈಸಿದಿರಾ?",
                     "hi": "“{place}” नहीं मिला। क्या आपका मतलब इनमें से कोई था?"},
    "same_airport": {"en": "The departure and arrival airport can't both be {code}.",
                     "kn": "ಹೊರಡುವ ಮತ್ತು ತಲುಪುವ ವಿಮಾನ ನಿಲ್ದಾಣ ಎರಡೂ {code} ಆಗಿರಲು ಸಾಧ್ಯವಿಲ್ಲ.",
                     "hi": "प्रस्थान और आगमन हवाई अड्डा दोनों {code} नहीं हो सकते।"},
    "date_past": {"en": "That date is in the past. Please choose {today} or later.",
                  "kn": "ಆ ದಿನಾಂಕ ಈಗಾಗಲೇ ಕಳೆದಿದೆ. ದಯವಿಟ್ಟು {today} ಅಥವಾ ನಂತರದ ದಿನಾಂಕ ಆರಿಸಿ.",
                  "hi": "वह तारीख बीत चुकी है। कृपया {today} या उसके बाद की तारीख चुनें।"},
    "date_invalid": {"en": "That doesn't look like a real calendar date. Could you check it?",
                     "kn": "ಅದು ಸರಿಯಾದ ದಿನಾಂಕದಂತೆ ಕಾಣುತ್ತಿಲ್ಲ. ದಯವಿಟ್ಟು ಪರಿಶೀಲಿಸುವಿರಾ?",
                     "hi": "यह सही तारीख नहीं लगती। क्या आप जाँच लेंगे?"},
    "date_too_far": {"en": "Sample schedules only go about a year ahead. Please pick an earlier date.",
                     "kn": "ಮಾದರಿ ವೇಳಾಪಟ್ಟಿಗಳು ಸುಮಾರು ಒಂದು ವರ್ಷದವರೆಗೆ ಮಾತ್ರ. ದಯವಿಟ್ಟು ಮುಂಚಿನ ದಿನಾಂಕ ಆರಿಸಿ.",
                     "hi": "सैंपल शेड्यूल लगभग एक साल आगे तक ही हैं। कृपया पहले की तारीख चुनें।"},
    "return_before_depart": {"en": "The return has to be after the departure ({date}).",
                             "kn": "ಹಿಂತಿರುಗುವಿಕೆ ಹೊರಡುವ ದಿನಾಂಕದ ({date}) ನಂತರ ಇರಬೇಕು.",
                             "hi": "वापसी प्रस्थान ({date}) के बाद होनी चाहिए।"},
    "pax_invalid": {"en": "Please include at least 1 adult, and at most {max} travellers with seats.",
                    "kn": "ಕನಿಷ್ಠ 1 ವಯಸ್ಕರು ಇರಬೇಕು ಮತ್ತು ಗರಿಷ್ಠ {max} ಸೀಟು ಪ್ರಯಾಣಿಕರು.",
                    "hi": "कम से कम 1 वयस्क और अधिकतम {max} सीट वाले यात्री होने चाहिए।"},
    "pax_infants": {"en": "Each infant needs an accompanying adult, so I've limited infants to the number of adults.",
                    "kn": "ಪ್ರತಿ ಶಿಶುವಿಗೆ ಜೊತೆಗೆ ಒಬ್ಬ ವಯಸ್ಕರು ಬೇಕು, ಆದ್ದರಿಂದ ಶಿಶುಗಳ ಸಂಖ್ಯೆಯನ್ನು ವಯಸ್ಕರ ಸಂಖ್ಯೆಗೆ ಸೀಮಿತಗೊಳಿಸಿದ್ದೇನೆ.",
                    "hi": "हर शिशु के साथ एक वयस्क ज़रूरी है, इसलिए शिशुओं की संख्या वयस्कों तक सीमित की है।"},
    # multi-city
    "mc_intro": {"en": "What's the first flight? For example: Bengaluru to Delhi on 10 Oct.",
                 "kn": "ಮೊದಲ ವಿಮಾನ ಯಾವುದು? ಉದಾಹರಣೆ: 10 ಅಕ್ಟೋಬರ್ ಬೆಂಗಳೂರಿನಿಂದ ದೆಹಲಿಗೆ.",
                 "hi": "पहली फ़्लाइट कौन-सी है? जैसे: 10 अक्टूबर को बेंगलुरु से दिल्ली।"},
    "mc_ask_leg_route": {"en": "Flight {n}: where from and where to?", "kn": "ವಿಮಾನ {n}: ಎಲ್ಲಿಂದ ಎಲ್ಲಿಗೆ?", "hi": "फ़्लाइट {n}: कहाँ से कहाँ?"},
    "mc_ask_leg_dest": {"en": "Flight {n} leaves from {origin}. Where to?", "kn": "ವಿಮಾನ {n} {origin} ನಿಂದ ಹೊರಡುತ್ತದೆ. ಎಲ್ಲಿಗೆ?",
                        "hi": "फ़्लाइट {n} {origin} से है। कहाँ तक?"},
    "mc_ask_next_dest": {"en": "Flight {n} continues from {origin}, where the previous flight lands. Where to? (You can also give a different starting city.)",
                         "kn": "ವಿಮಾನ {n} ಹಿಂದಿನ ವಿಮಾನ ಇಳಿಯುವ {origin} ನಿಂದ ಮುಂದುವರಿಯುತ್ತದೆ. ಎಲ್ಲಿಗೆ? (ಬೇರೆ ಆರಂಭಿಕ ನಗರವನ್ನೂ ಹೇಳಬಹುದು.)",
                         "hi": "फ़्लाइट {n} {origin} से आगे, जहाँ पिछली फ़्लाइट उतरती है। कहाँ तक? (आप कोई और शुरुआती शहर भी बता सकते हैं।)"},
    "mc_ask_leg_date": {"en": "What date is flight {n}, {route}?", "kn": "ವಿಮಾನ {n}, {route}, ಯಾವ ದಿನಾಂಕ?",
                        "hi": "फ़्लाइट {n}, {route}, किस तारीख को?"},
    "mc_more": {"en": "That's {n} flights. Add another, or search these?", "kn": "ಒಟ್ಟು {n} ವಿಮಾನಗಳು. ಇನ್ನೊಂದು ಸೇರಿಸಲೇ ಅಥವಾ ಇವನ್ನು ಹುಡುಕಲೇ?",
                "hi": "कुल {n} फ़्लाइट। एक और जोड़ें या इन्हें खोजें?"},
    "mc_max": {"en": "A multi-city trip can have up to {n} flights here.", "kn": "ಇಲ್ಲಿ ಮಲ್ಟಿ-ಸಿಟಿ ಪ್ರವಾಸದಲ್ಲಿ ಗರಿಷ್ಠ {n} ವಿಮಾನಗಳು.",
               "hi": "यहाँ मल्टी-सिटी यात्रा में अधिकतम {n} फ़्लाइट हो सकती हैं।"},
    "leg_removed": {"en": "Removed flight {n}.", "kn": "ವಿಮಾನ {n} ತೆಗೆದುಹಾಕಲಾಗಿದೆ.", "hi": "फ़्लाइट {n} हटा दी गई।"},
    "leg_order": {"en": "Flight {n} can't be before flight {prev} ({date}). Please pick another date.",
                  "kn": "ವಿಮಾನ {n}, ವಿಮಾನ {prev} ({date}) ಕ್ಕಿಂತ ಮೊದಲು ಇರಲು ಸಾಧ್ಯವಿಲ್ಲ. ಬೇರೆ ದಿನಾಂಕ ಆರಿಸಿ.",
                  "hi": "फ़्लाइट {n}, फ़्लाइट {prev} ({date}) से पहले नहीं हो सकती। दूसरी तारीख चुनें।"},
    # results
    "flights_found_one": {"en": "Here are sample one-way options for {pax}, {cabin}. Pick one to continue.",
                          "kn": "{pax}, {cabin} ಗಾಗಿ ಮಾದರಿ ಒನ್-ವೇ ಆಯ್ಕೆಗಳು ಇಲ್ಲಿವೆ. ಮುಂದುವರೆಯಲು ಒಂದನ್ನು ಆರಿಸಿ.",
                          "hi": "{pax}, {cabin} के लिए सैंपल वन-वे विकल्प ये हैं। आगे बढ़ने के लिए एक चुनें।"},
    "flights_found_round": {"en": "Here are sample options for {pax}, {cabin}. Pick one outbound and one return flight.",
                            "kn": "{pax}, {cabin} ಗಾಗಿ ಮಾದರಿ ಆಯ್ಕೆಗಳು. ಹೋಗುವ ಒಂದು ಮತ್ತು ಹಿಂತಿರುಗುವ ಒಂದು ವಿಮಾನ ಆರಿಸಿ.",
                            "hi": "{pax}, {cabin} के लिए सैंपल विकल्प। एक जाने की और एक वापसी की फ़्लाइट चुनें।"},
    "flights_found_multi": {"en": "Here are sample options for each of your {n} flights ({pax}, {cabin}). Pick one per flight.",
                            "kn": "ನಿಮ್ಮ {n} ವಿಮಾನಗಳಿಗೆ ({pax}, {cabin}) ಮಾದರಿ ಆಯ್ಕೆಗಳು. ಪ್ರತಿಯೊಂದಕ್ಕೂ ಒಂದನ್ನು ಆರಿಸಿ.",
                            "hi": "आपकी {n} फ़्लाइट ({pax}, {cabin}) के लिए सैंपल विकल्प। हर फ़्लाइट के लिए एक चुनें।"},
    "flights_still_shown": {"en": "The sample flights are shown above. Pick one, or tell me what to change.",
                            "kn": "ಮಾದರಿ ವಿಮಾನಗಳು ಮೇಲೆ ಇವೆ. ಒಂದನ್ನು ಆರಿಸಿ ಅಥವಾ ಏನು ಬದಲಾಯಿಸಬೇಕು ಎಂದು ಹೇಳಿ.",
                            "hi": "सैंपल फ़्लाइट ऊपर दिख रही हैं। एक चुनें या बताइए क्या बदलना है।"},
    "no_sample_flights": {"en": "I don't have sample flights for that route.", "kn": "ಆ ಮಾರ್ಗಕ್ಕೆ ಮಾದರಿ ವಿಮಾನಗಳಿಲ್ಲ.",
                          "hi": "उस रूट के लिए सैंपल फ़्लाइट नहीं हैं।"},
    "leg_title_one": {"en": "Flight", "kn": "ವಿಮಾನ", "hi": "फ़्लाइट"},
    "leg_title_outbound": {"en": "Outbound", "kn": "ಹೋಗುವ ವಿಮಾನ", "hi": "जाने की फ़्लाइट"},
    "leg_title_return": {"en": "Return", "kn": "ಹಿಂತಿರುಗುವ ವಿಮಾನ", "hi": "वापसी की फ़्लाइट"},
    "leg_title_n": {"en": "Flight {n}", "kn": "ವಿಮಾನ {n}", "hi": "फ़्लाइट {n}"},
    "flight_selected": {"en": "Selected {flight} ({route}).", "kn": "{flight} ({route}) ಆಯ್ಕೆಯಾಗಿದೆ.", "hi": "{flight} ({route}) चुनी गई।"},
    "pick_return": {"en": "Now pick your return flight.", "kn": "ಈಗ ಹಿಂತಿರುಗುವ ವಿಮಾನ ಆರಿಸಿ.", "hi": "अब वापसी की फ़्लाइट चुनें।"},
    "pick_leg": {"en": "Now pick flight {n}.", "kn": "ಈಗ ವಿಮಾನ {n} ಆರಿಸಿ.", "hi": "अब फ़्लाइट {n} चुनें।"},
    "offer_hotel": {"en": "Would you like a hotel in {city} too?", "kn": "{city} ನಲ್ಲಿ ಹೋಟೆಲ್ ಕೂಡ ಬೇಕೇ?", "hi": "क्या {city} में होटल भी चाहिए?"},
    "option_gone": {"en": "That option isn't in the current results any more. Please pick from the latest cards.",
                    "kn": "ಆ ಆಯ್ಕೆ ಈಗಿನ ಫಲಿತಾಂಶಗಳಲ್ಲಿ ಇಲ್ಲ. ದಯವಿಟ್ಟು ಇತ್ತೀಚಿನ ಕಾರ್ಡ್‌ಗಳಿಂದ ಆರಿಸಿ.",
                    "hi": "वह विकल्प अब मौजूदा नतीजों में नहीं है। कृपया नए कार्ड से चुनें।"},
    # ---------------- hotels
    "ask_hotel_city": {"en": "Which city do you need a hotel in?", "kn": "ಯಾವ ನಗರದಲ್ಲಿ ಹೋಟೆಲ್ ಬೇಕು?", "hi": "किस शहर में होटल चाहिए?"},
    "ask_checkin": {"en": "When do you check in at {city}?", "kn": "{city} ನಲ್ಲಿ ಯಾವ ದಿನ ಚೆಕ್-ಇನ್?", "hi": "{city} में चेक-इन कब है?"},
    "ask_checkout": {"en": "Check-out date, or how many nights from {date}?", "kn": "ಚೆಕ್-ಔಟ್ ದಿನಾಂಕ, ಅಥವಾ {date} ರಿಂದ ಎಷ್ಟು ರಾತ್ರಿ?",
                     "hi": "चेक-आउट की तारीख, या {date} से कितनी रातें?"},
    "ask_guests": {"en": "How many guests?", "kn": "ಎಷ್ಟು ಅತಿಥಿಗಳು?", "hi": "कितने मेहमान?"},
    "ack_hotel_city": {"en": "hotel in {city}", "kn": "{city} ನಲ್ಲಿ ಹೋಟೆಲ್", "hi": "{city} में होटल"},
    "ack_checkin": {"en": "check-in {date}", "kn": "ಚೆಕ್-ಇನ್ {date}", "hi": "चेक-इन {date}"},
    "ack_checkout": {"en": "check-out {date}", "kn": "ಚೆಕ್-ಔಟ್ {date}", "hi": "चेक-आउट {date}"},
    "hotel_city_unsupported": {"en": "I don't have sample hotels in {city} yet. Available: {list}.",
                               "kn": "{city} ನಲ್ಲಿ ಇನ್ನೂ ಮಾದರಿ ಹೋಟೆಲ್‌ಗಳಿಲ್ಲ. ಲಭ್ಯವಿರುವವು: {list}.",
                               "hi": "{city} में अभी सैंपल होटल नहीं हैं। उपलब्ध: {list}।"},
    "checkout_before": {"en": "Check-out must be after check-in ({date}).", "kn": "ಚೆಕ್-ಔಟ್ ಚೆಕ್-ಇನ್ ({date}) ನಂತರ ಇರಬೇಕು.",
                        "hi": "चेक-आउट, चेक-इन ({date}) के बाद होना चाहिए।"},
    "too_many_nights": {"en": "For this demo I can price stays of up to {n} nights.", "kn": "ಈ ಡೆಮೊದಲ್ಲಿ ಗರಿಷ್ಠ {n} ರಾತ್ರಿಗಳ ತಂಗುವಿಕೆ ಮಾತ್ರ.",
                        "hi": "इस डेमो में अधिकतम {n} रातों का ठहराव ही संभव है।"},
    "note_prefilled": {"en": "I've used your flight dates and travellers.", "kn": "ನಿಮ್ಮ ವಿಮಾನದ ದಿನಾಂಕಗಳು ಮತ್ತು ಪ್ರಯಾಣಿಕರ ವಿವರ ಬಳಸಿದ್ದೇನೆ.",
                       "hi": "मैंने आपकी फ़्लाइट की तारीखें और यात्री जानकारी इस्तेमाल की है।"},
    "hotels_found": {"en": "Here are {n} sample hotels in {city}: {checkin} – {checkout}, {nights} nights, {guests}, {rooms} room(s). Prices are indicative.",
                     "kn": "{city} ನಲ್ಲಿ {n} ಮಾದರಿ ಹೋಟೆಲ್‌ಗಳು: {checkin} – {checkout}, {nights} ರಾತ್ರಿ, {guests}, {rooms} ಕೊಠಡಿ. ಬೆಲೆಗಳು ಅಂದಾಜು.",
                     "hi": "{city} में {n} सैंपल होटल: {checkin} – {checkout}, {nights} रातें, {guests}, {rooms} कमरे। कीमतें अनुमानित हैं।"},
    "hotels_still_shown": {"en": "The sample hotels are shown above. Pick one, or tell me what to change.",
                           "kn": "ಮಾದರಿ ಹೋಟೆಲ್‌ಗಳು ಮೇಲೆ ಇವೆ. ಒಂದನ್ನು ಆರಿಸಿ ಅಥವಾ ಏನು ಬದಲಾಯಿಸಬೇಕು ಹೇಳಿ.",
                           "hi": "सैंपल होटल ऊपर दिख रहे हैं। एक चुनें या बताइए क्या बदलना है।"},
    "hotel_selected": {"en": "Selected {hotel}.", "kn": "{hotel} ಆಯ್ಕೆಯಾಗಿದೆ.", "hi": "{hotel} चुना गया।"},
    # ---------------- review / checkout / alert / seats
    "review_nothing": {"en": "You haven't selected a flight or hotel yet.", "kn": "ನೀವು ಇನ್ನೂ ವಿಮಾನ ಅಥವಾ ಹೋಟೆಲ್ ಆರಿಸಿಲ್ಲ.",
                       "hi": "आपने अभी तक कोई फ़्लाइट या होटल नहीं चुना है।"},
    "review_missing_leg": {"en": "Please pick flight {n} first.", "kn": "ದಯವಿಟ್ಟು ಮೊದಲು ವಿಮಾನ {n} ಆರಿಸಿ.", "hi": "कृपया पहले फ़्लाइट {n} चुनें।"},
    "review_intro": {"en": "Here's your trip summary. All prices are sample data.",
                     "kn": "ನಿಮ್ಮ ಪ್ರವಾಸದ ಸಾರಾಂಶ ಇಲ್ಲಿದೆ. ಎಲ್ಲಾ ಬೆಲೆಗಳು ಮಾದರಿ ಡೇಟಾ.",
                     "hi": "यह रहा आपकी यात्रा का सारांश। सभी कीमतें सैंपल डेटा हैं।"},
    "checkout_done": {"en": "Demo checkout finished. No payment was taken, no reservation was made and no PNR was issued.",
                      "kn": "ಡೆಮೊ ಚೆಕ್‌ಔಟ್ ಮುಗಿದಿದೆ. ಯಾವುದೇ ಪಾವತಿ ತೆಗೆದುಕೊಂಡಿಲ್ಲ, ಯಾವುದೇ ಕಾಯ್ದಿರಿಸುವಿಕೆ ಮಾಡಿಲ್ಲ ಮತ್ತು PNR ನೀಡಿಲ್ಲ.",
                      "hi": "डेमो चेकआउट पूरा हुआ। कोई भुगतान नहीं लिया गया, कोई आरक्षण नहीं हुआ और कोई PNR जारी नहीं हुआ।"},
    "alert_need_flight": {"en": "Select a sample flight first, then I can show a simulated update for it.",
                          "kn": "ಮೊದಲು ಒಂದು ಮಾದರಿ ವಿಮಾನ ಆರಿಸಿ, ನಂತರ ಅದಕ್ಕೆ ಅನುಕರಣೆಯ ಅಪ್‌ಡೇಟ್ ತೋರಿಸುತ್ತೇನೆ.",
                          "hi": "पहले एक सैंपल फ़्लाइट चुनें, फिर मैं उसका सिम्युलेटेड अपडेट दिखाऊँगी।"},
    "alert_text": {"en": "Simulated update for {flight} ({route}, {date}): departure moved from {old} to {new}, a {mins}-minute delay. This is a demo; no live airline feed is connected.",
                   "kn": "{flight} ({route}, {date}) ಗಾಗಿ ಅನುಕರಣೆಯ ಅಪ್‌ಡೇಟ್: ಹೊರಡುವ ಸಮಯ {old} ರಿಂದ {new} ಗೆ, {mins} ನಿಮಿಷ ವಿಳಂಬ. ಇದು ಡೆಮೊ; ಯಾವುದೇ ಲೈವ್ ಏರ್‌ಲೈನ್ ಮಾಹಿತಿ ಸಂಪರ್ಕದಲ್ಲಿಲ್ಲ.",
                   "hi": "{flight} ({route}, {date}) का सिम्युलेटेड अपडेट: प्रस्थान {old} से {new}, {mins} मिनट की देरी। यह डेमो है; कोई लाइव एयरलाइन फ़ीड जुड़ी नहीं है।"},
    "seats_open": {"en": "Opening the sample seat map for {flight}.", "kn": "{flight} ಗಾಗಿ ಮಾದರಿ ಸೀಟ್ ನಕ್ಷೆ ತೆರೆಯುತ್ತಿದೆ.",
                   "hi": "{flight} का सैंपल सीट मैप खुल रहा है।"},
    "seats_saved": {"en": "Seats noted for the demo: {seats}.", "kn": "ಡೆಮೊಗಾಗಿ ಸೀಟುಗಳು ದಾಖಲಾಗಿವೆ: {seats}.", "hi": "डेमो के लिए सीटें दर्ज: {seats}।"},
    "seats_invalid": {"en": "I couldn't save those seats. Please choose them again.", "kn": "ಆ ಸೀಟುಗಳನ್ನು ಉಳಿಸಲಾಗಲಿಲ್ಲ. ಮತ್ತೆ ಆರಿಸಿ.",
                      "hi": "वे सीटें सेव नहीं हो सकीं। कृपया फिर से चुनें।"},
    "back_from_seats": {"en": "Back from the seat map. You can review your trip or change seats.",
                        "kn": "ಸೀಟ್ ನಕ್ಷೆಯಿಂದ ಹಿಂತಿರುಗಿದ್ದೀರಿ. ಪ್ರವಾಸ ಪರಿಶೀಲಿಸಬಹುದು ಅಥವಾ ಸೀಟು ಬದಲಾಯಿಸಬಹುದು.",
                        "hi": "सीट मैप से वापस। आप यात्रा की समीक्षा कर सकते हैं या सीटें बदल सकते हैं।"},
    "seat_line": {"en": "Seats, flight {leg}", "kn": "ಸೀಟುಗಳು, ವಿಮಾನ {leg}", "hi": "सीटें, फ़्लाइट {leg}"},
    # ---------------- plan
    "plan_ask_dest": {"en": "Where would you like to go? I have curated sample plans for {list}.",
                      "kn": "ನೀವು ಎಲ್ಲಿಗೆ ಹೋಗಲು ಬಯಸುತ್ತೀರಿ? ನನ್ನ ಬಳಿ {list} ಗಾಗಿ ಆಯ್ದ ಮಾದರಿ ಯೋಜನೆಗಳಿವೆ.",
                      "hi": "आप कहाँ जाना चाहेंगे? मेरे पास {list} की चुनी हुई सैंपल योजनाएँ हैं।"},
    "plan_unsupported": {"en": "I don't have a curated plan for {place} yet, and I won't make one up. Available plans: {list}.",
                         "kn": "{place} ಗಾಗಿ ಇನ್ನೂ ಆಯ್ದ ಯೋಜನೆ ಇಲ್ಲ, ಮತ್ತು ನಾನು ಊಹಿಸಿ ರಚಿಸುವುದಿಲ್ಲ. ಲಭ್ಯವಿರುವ ಯೋಜನೆಗಳು: {list}.",
                         "hi": "{place} के लिए अभी कोई चुनी हुई योजना नहीं है, और मैं अंदाज़े से नहीं बनाऊँगी। उपलब्ध योजनाएँ: {list}।"},
    "plan_ask_days": {"en": "How many days? The {dest} plan works for {min}–{max} days.",
                      "kn": "ಎಷ್ಟು ದಿನ? {dest} ಯೋಜನೆ {min}–{max} ದಿನಗಳಿಗೆ ಸೂಕ್ತ.",
                      "hi": "कितने दिन? {dest} योजना {min}–{max} दिनों के लिए है।"},
    "plan_days_range": {"en": "The {dest} plan is designed for {min}–{max} days, so I can't stretch it to {days} days without inventing content. Shall I use {closest} days?",
                        "kn": "{dest} ಯೋಜನೆ {min}–{max} ದಿನಗಳಿಗೆ ರೂಪಿಸಲಾಗಿದೆ, ಆದ್ದರಿಂದ ಊಹಿಸದೆ {days} ದಿನಗಳಿಗೆ ವಿಸ್ತರಿಸಲಾಗದು. {closest} ದಿನ ಬಳಸಲೇ?",
                        "hi": "{dest} योजना {min}–{max} दिनों के लिए बनी है, इसलिए बिना कुछ गढ़े इसे {days} दिन नहीं कर सकती। क्या {closest} दिन रखूँ?"},
    "plan_ask_prefs": {"en": "Any preferences? Budget, Luxury, Adventure, Family or Culture, or type your own.",
                       "kn": "ಯಾವುದಾದರೂ ಆದ್ಯತೆ? ಬಜೆಟ್, ಐಷಾರಾಮಿ, ಸಾಹಸ, ಕುಟುಂಬ ಅಥವಾ ಸಂಸ್ಕೃತಿ, ಅಥವಾ ನಿಮ್ಮದೇ ಬರೆಯಿರಿ.",
                       "hi": "कोई पसंद? बजट, लक्ज़री, एडवेंचर, परिवार या संस्कृति, या अपनी पसंद लिखें।"},
    "plan_result": {"en": "Here's a {days}-day {dest} plan.", "kn": "ಇಲ್ಲಿದೆ {days} ದಿನಗಳ {dest} ಯೋಜನೆ.", "hi": "यह रही {days} दिन की {dest} योजना।"},
    "plan_title": {"en": "{days} days in {dest}", "kn": "{dest} ನಲ್ಲಿ {days} ದಿನ", "hi": "{dest} में {days} दिन"},
    "plan_adjusted": {"en": "It's an adjusted version of a curated sample, based on what you asked for.",
                      "kn": "ನೀವು ಕೇಳಿದಂತೆ ಹೊಂದಿಸಲಾದ ಆಯ್ದ ಮಾದರಿಯ ಆವೃತ್ತಿ ಇದು.",
                      "hi": "यह आपकी माँग के अनुसार बदली गई एक चुनी हुई सैंपल योजना है।"},
    "plan_pref_unsupported": {"en": "The sample content doesn't cover “{pref}” for these days, so I kept the standard activities.",
                              "kn": "ಈ ದಿನಗಳಿಗೆ ಮಾದರಿ ವಿಷಯದಲ್ಲಿ “{pref}” ಇಲ್ಲ, ಆದ್ದರಿಂದ ಸಾಮಾನ್ಯ ಚಟುವಟಿಕೆಗಳನ್ನು ಉಳಿಸಿದ್ದೇನೆ.",
                              "hi": "इन दिनों के सैंपल में “{pref}” शामिल नहीं है, इसलिए सामान्य गतिविधियाँ रखी हैं।"},
    "plan_budget_adjusted": {"en": "To fit {amount}, I've switched to the {style} level.",
                             "kn": "{amount} ಒಳಗೆ ಹೊಂದಿಸಲು {style} ಮಟ್ಟಕ್ಕೆ ಬದಲಾಯಿಸಿದ್ದೇನೆ.",
                             "hi": "{amount} में समाने के लिए {style} स्तर चुना है।"},
    "unknown_place": {"en": "I couldn't find “{place}” in my airport list.", "kn": "ನನ್ನ ವಿಮಾನ ನಿಲ್ದಾಣ ಪಟ್ಟಿಯಲ್ಲಿ “{place}” ಸಿಗಲಿಲ್ಲ.",
                      "hi": "मेरी हवाई अड्डा सूची में “{place}” नहीं मिला।"},
    "plan_over_budget": {"en": "Even the budget level is above {amount} for this plan.",
                         "kn": "ಈ ಯೋಜನೆಗೆ ಬಜೆಟ್ ಮಟ್ಟವೂ {amount} ಕ್ಕಿಂತ ಹೆಚ್ಚು.",
                         "hi": "इस योजना के लिए बजट स्तर भी {amount} से ज़्यादा है।"},
    # ---------------- labels used inside replies
    "n_adults": {"en": ("{n} adult", "{n} adults"), "kn": ("{n} ವಯಸ್ಕ", "{n} ವಯಸ್ಕರು"), "hi": "{n} वयस्क"},
    "n_children": {"en": ("{n} child", "{n} children"), "kn": ("{n} ಮಗು", "{n} ಮಕ್ಕಳು"), "hi": ("{n} बच्चा", "{n} बच्चे")},
    "n_infants": {"en": ("{n} infant", "{n} infants"), "kn": ("{n} ಶಿಶು", "{n} ಶಿಶುಗಳು"), "hi": "{n} शिशु"},
    "n_nights": {"en": ("{n} night", "{n} nights"), "kn": "{n} ರಾತ್ರಿ", "hi": ("{n} रात", "{n} रातें")},
    "n_rooms": {"en": ("{n} room", "{n} rooms"), "kn": "{n} ಕೊಠಡಿ", "hi": ("{n} कमरा", "{n} कमरे")},
    "n_days": {"en": ("{n} day", "{n} days"), "kn": "{n} ದಿನ", "hi": "{n} दिन"},
    "cabin_Economy": {"en": "Economy", "kn": "ಎಕಾನಮಿ", "hi": "इकॉनमी"},
    "cabin_Premium_Economy": {"en": "Premium Economy", "kn": "ಪ್ರೀಮಿಯಂ ಎಕಾನಮಿ", "hi": "प्रीमियम इकॉनमी"},
    "cabin_Business": {"en": "Business", "kn": "ಬಿಸಿನೆಸ್", "hi": "बिज़नेस"},
    "cabin_First": {"en": "First", "kn": "ಫಸ್ಟ್", "hi": "फ़र्स्ट"},
    "interest_budget": {"en": "Budget", "kn": "ಬಜೆಟ್", "hi": "बजट"},
    "interest_luxury": {"en": "Luxury", "kn": "ಐಷಾರಾಮಿ", "hi": "लक्ज़री"},
    "interest_adventure": {"en": "Adventure", "kn": "ಸಾಹಸ", "hi": "एडवेंचर"},
    "interest_family": {"en": "Family", "kn": "ಕುಟುಂಬ", "hi": "परिवार"},
    "interest_culture": {"en": "Culture", "kn": "ಸಂಸ್ಕೃತಿ", "hi": "संस्कृति"},
    "style_budget": {"en": "budget", "kn": "ಬಜೆಟ್", "hi": "बजट"},
    "style_standard": {"en": "standard", "kn": "ಸಾಮಾನ್ಯ", "hi": "स्टैंडर्ड"},
    "style_luxury": {"en": "luxury", "kn": "ಐಷಾರಾಮಿ", "hi": "लक्ज़री"},
    # ---------------- quick replies
    "qr_book_flight": {"en": "✈️ Book a flight", "kn": "✈️ ವಿಮಾನ ಬುಕ್ ಮಾಡಿ", "hi": "✈️ फ़्लाइट बुक करें"},
    "qr_find_hotel": {"en": "🏨 Find a hotel", "kn": "🏨 ಹೋಟೆಲ್ ಹುಡುಕಿ", "hi": "🏨 होटल खोजें"},
    "qr_plan_trip": {"en": "🗺️ Plan a trip", "kn": "🗺️ ಪ್ರವಾಸ ಯೋಜಿಸಿ", "hi": "🗺️ यात्रा प्लान करें"},
    "qr_one_way": {"en": "One-way", "kn": "ಒನ್-ವೇ", "hi": "वन-वे"},
    "qr_round_trip": {"en": "Round-trip", "kn": "ರೌಂಡ್-ಟ್ರಿಪ್", "hi": "राउंड-ट्रिप"},
    "qr_multi_city": {"en": "Multi-city", "kn": "ಮಲ್ಟಿ-ಸಿಟಿ", "hi": "मल्टी-सिटी"},
    "qr_add_flight": {"en": "➕ Add another flight", "kn": "➕ ಇನ್ನೊಂದು ವಿಮಾನ ಸೇರಿಸಿ", "hi": "➕ एक और फ़्लाइट जोड़ें"},
    "qr_search_flights": {"en": "🔎 Search flights", "kn": "🔎 ವಿಮಾನ ಹುಡುಕಿ", "hi": "🔎 फ़्लाइट खोजें"},
    "qr_flights_to": {"en": "✈️ Flights to {place}", "kn": "✈️ {place} ಗೆ ವಿಮಾನ", "hi": "✈️ {place} की फ़्लाइट"},
    "qr_hotels_in": {"en": "🏨 Hotels in {place}", "kn": "🏨 {place} ನಲ್ಲಿ ಹೋಟೆಲ್", "hi": "🏨 {place} में होटल"},
    "qr_plan_for": {"en": "🗺️ Plan a {place} trip", "kn": "🗺️ {place} ಪ್ರವಾಸ ಯೋಜನೆ", "hi": "🗺️ {place} यात्रा योजना"},
    "qr_flying_from": {"en": "Flying from {place}", "kn": "{place} ನಿಂದ ಹೊರಡುವುದು", "hi": "{place} से उड़ान"},
    "qr_flying_to": {"en": "Going to {place}", "kn": "{place} ಗೆ ಹೋಗುವುದು", "hi": "{place} जाना है"},
    "qr_departure": {"en": "Departure", "kn": "ಹೊರಡುವ ದಿನ", "hi": "प्रस्थान"},
    "qr_return": {"en": "Return", "kn": "ಹಿಂತಿರುಗುವ ದಿನ", "hi": "वापसी"},
    "qr_review": {"en": "🧾 Review trip", "kn": "🧾 ಪ್ರವಾಸ ಪರಿಶೀಲಿಸಿ", "hi": "🧾 यात्रा देखें"},
    "qr_checkout": {"en": "Demo checkout", "kn": "ಡೆಮೊ ಚೆಕ್‌ಔಟ್", "hi": "डेमो चेकआउट"},
    "qr_add_hotel": {"en": "🏨 Add a hotel", "kn": "🏨 ಹೋಟೆಲ್ ಸೇರಿಸಿ", "hi": "🏨 होटल जोड़ें"},
    "qr_seats": {"en": "💺 Choose seats (demo)", "kn": "💺 ಸೀಟು ಆರಿಸಿ (ಡೆಮೊ)", "hi": "💺 सीट चुनें (डेमो)"},
    "qr_simulate": {"en": "⏱️ Simulated flight update", "kn": "⏱️ ಅನುಕರಣೆಯ ವಿಮಾನ ಅಪ್‌ಡೇಟ್", "hi": "⏱️ सिम्युलेटेड फ़्लाइट अपडेट"},
    "qr_start_over": {"en": "Start over", "kn": "ಹೊಸದಾಗಿ ಪ್ರಾರಂಭಿಸಿ", "hi": "फिर से शुरू करें"},
    "qr_no_pref": {"en": "No preference", "kn": "ಯಾವುದೇ ಆದ್ಯತೆ ಇಲ್ಲ", "hi": "कोई पसंद नहीं"},
    "qr_change_prefs": {"en": "Change preferences", "kn": "ಆದ್ಯತೆ ಬದಲಾಯಿಸಿ", "hi": "पसंद बदलें"},
}

# Labels used by the browser (cards, controls). Served at /api/i18n/<lang>.
UI: dict[str, dict] = {
    "hero_title": {"en": "Hello, I'm Aura", "kn": "ನಮಸ್ಕಾರ, ನಾನು ಔರಾ", "hi": "नमस्ते, मैं ऑरा हूँ"},
    "hero_sub": {"en": "Flights, hotels and trip plans. Just ask.", "kn": "ವಿಮಾನ, ಹೋಟೆಲ್ ಮತ್ತು ಪ್ರವಾಸ ಯೋಜನೆ. ಕೇಳಿ ಸಾಕು.",
                 "hi": "फ़्लाइट, होटल और यात्रा योजना। बस पूछिए।"},
    "tagline": {"en": "Your travel partner", "kn": "ನಿಮ್ಮ ಪ್ರಯಾಣ ಸಂಗಾತಿ", "hi": "आपका यात्रा साथी"},
    "quick_actions": {"en": "Quick actions", "kn": "ತ್ವರಿತ ಕ್ರಿಯೆಗಳು", "hi": "त्वरित विकल्प"},
    "qa_flight": {"en": "✈️ Book a flight", "kn": "✈️ ವಿಮಾನ ಬುಕ್ ಮಾಡಿ", "hi": "✈️ फ़्लाइट बुक करें"},
    "qa_hotel": {"en": "🏨 Find a hotel", "kn": "🏨 ಹೋಟೆಲ್ ಹುಡುಕಿ", "hi": "🏨 होटल खोजें"},
    "qa_plan": {"en": "🗺️ Plan a trip", "kn": "🗺️ ಪ್ರವಾಸ ಯೋಜಿಸಿ", "hi": "🗺️ यात्रा प्लान करें"},
    "qa_visa": {"en": "🛂 Visa (international)", "kn": "🛂 ವೀಸಾ (ಅಂತರರಾಷ್ಟ್ರೀಯ)", "hi": "🛂 वीज़ा (अंतरराष्ट्रीय)"},
    "qa_insurance": {"en": "🛡️ Travel insurance", "kn": "🛡️ ಪ್ರಯಾಣ ವಿಮೆ", "hi": "🛡️ यात्रा बीमा"},
    "qa_human": {"en": "👤 Talk to a human", "kn": "👤 ಮಾನವರೊಂದಿಗೆ ಮಾತನಾಡಿ", "hi": "👤 इंसान से बात करें"},
    "reply_language": {"en": "Reply language", "kn": "ಉತ್ತರದ ಭಾಷೆ", "hi": "जवाब की भाषा"},
    "auto": {"en": "Auto (match my messages)", "kn": "ಸ್ವಯಂ (ನನ್ನ ಸಂದೇಶದಂತೆ)", "hi": "स्वतः (मेरे संदेश जैसा)"},
    "mic_language": {"en": "Speech recognition language", "kn": "ಧ್ವನಿ ಗುರುತಿಸುವಿಕೆಯ ಭಾಷೆ", "hi": "आवाज़ पहचान की भाषा"},
    "placeholder": {"en": "Message Aura…", "kn": "ಔರಾಗೆ ಸಂದೇಶ…", "hi": "ऑरा को संदेश…"},
    "send": {"en": "Send", "kn": "ಕಳುಹಿಸಿ", "hi": "भेजें"},
    "mic_start": {"en": "Start voice input", "kn": "ಧ್ವನಿ ಇನ್‌ಪುಟ್ ಪ್ರಾರಂಭಿಸಿ", "hi": "आवाज़ से लिखें"},
    "listening": {"en": "Listening…", "kn": "ಕೇಳುತ್ತಿದ್ದೇನೆ…", "hi": "सुन रही हूँ…"},
    "transcript_hint": {"en": "Check the transcript, edit it if needed, then press send.",
                        "kn": "ಪಠ್ಯವನ್ನು ಪರಿಶೀಲಿಸಿ, ಬೇಕಾದರೆ ತಿದ್ದಿ, ನಂತರ ಕಳುಹಿಸಿ.",
                        "hi": "लिखे हुए पाठ को जाँचें, ज़रूरत हो तो सुधारें, फिर भेजें।"},
    "voice_unsupported": {"en": "Voice input isn't supported in this browser. Please type instead.",
                          "kn": "ಈ ಬ್ರೌಸರ್‌ನಲ್ಲಿ ಧ್ವನಿ ಇನ್‌ಪುಟ್ ಬೆಂಬಲಿತವಿಲ್ಲ. ದಯವಿಟ್ಟು ಟೈಪ್ ಮಾಡಿ.",
                          "hi": "इस ब्राउज़र में आवाज़ इनपुट समर्थित नहीं है। कृपया टाइप करें।"},
    "voice_error": {"en": "I couldn't hear that. Please try again or type.", "kn": "ಕೇಳಿಸಲಿಲ್ಲ. ಮತ್ತೆ ಪ್ರಯತ್ನಿಸಿ ಅಥವಾ ಟೈಪ್ ಮಾಡಿ.",
                    "hi": "सुनाई नहीं दिया। फिर से कोशिश करें या टाइप करें।"},
    "voice_reply": {"en": "Read replies aloud", "kn": "ಉತ್ತರಗಳನ್ನು ಓದಿ ಹೇಳು", "hi": "जवाब बोलकर सुनाएँ"},
    "thinking": {"en": "Aura is thinking", "kn": "ಔರಾ ಯೋಚಿಸುತ್ತಿದ್ದಾಳೆ", "hi": "ऑरा सोच रही है"},
    "server_error": {"en": "Sorry, I couldn't reach the server. Please try again.", "kn": "ಕ್ಷಮಿಸಿ, ಸರ್ವರ್ ತಲುಪಲಾಗಲಿಲ್ಲ. ಮತ್ತೆ ಪ್ರಯತ್ನಿಸಿ.",
                     "hi": "माफ़ कीजिए, सर्वर से संपर्क नहीं हो सका। फिर से कोशिश करें।"},
    "sample_data": {"en": "Sample data", "kn": "ಮಾದರಿ ಡೇಟಾ", "hi": "सैंपल डेटा"},
    "sample_note": {"en": "Sample prices and availability for demonstration only.",
                    "kn": "ಬೆಲೆಗಳು ಮತ್ತು ಲಭ್ಯತೆ ಪ್ರದರ್ಶನಕ್ಕಾಗಿ ಮಾತ್ರ ಮಾದರಿ.",
                    "hi": "कीमतें और उपलब्धता केवल प्रदर्शन के लिए सैंपल हैं।"},
    "select": {"en": "Select", "kn": "ಆರಿಸಿ", "hi": "चुनें"},
    "selected": {"en": "Selected ✓", "kn": "ಆಯ್ಕೆಯಾಗಿದೆ ✓", "hi": "चुना गया ✓"},
    "nonstop": {"en": "Non-stop", "kn": "ನಿಲ್ಲದ", "hi": "नॉन-स्टॉप"},
    "one_stop_via": {"en": "1 stop via {via}", "kn": "{via} ಮೂಲಕ 1 ನಿಲುಗಡೆ", "hi": "{via} होकर 1 स्टॉप"},
    "per_adult": {"en": "per adult", "kn": "ಪ್ರತಿ ವಯಸ್ಕರಿಗೆ", "hi": "प्रति वयस्क"},
    "for_travellers": {"en": "total for travellers", "kn": "ಪ್ರಯಾಣಿಕರಿಗೆ ಒಟ್ಟು", "hi": "यात्रियों का कुल"},
    "next_day": {"en": "+{n} day", "kn": "+{n} ದಿನ", "hi": "+{n} दिन"},
    "per_night": {"en": "per night", "kn": "ಪ್ರತಿ ರಾತ್ರಿ", "hi": "प्रति रात"},
    "stay_total": {"en": "{nights} nights · {rooms} room(s)", "kn": "{nights} ರಾತ್ರಿ · {rooms} ಕೊಠಡಿ", "hi": "{nights} रात · {rooms} कमरे"},
    "rating": {"en": "rating", "kn": "ರೇಟಿಂಗ್", "hi": "रेटिंग"},
    "review_title": {"en": "Trip summary", "kn": "ಪ್ರವಾಸ ಸಾರಾಂಶ", "hi": "यात्रा सारांश"},
    "total_indicative": {"en": "Indicative total", "kn": "ಅಂದಾಜು ಒಟ್ಟು", "hi": "अनुमानित कुल"},
    "demo_checkout": {"en": "Demo checkout", "kn": "ಡೆಮೊ ಚೆಕ್‌ಔಟ್", "hi": "डेमो चेकआउट"},
    "checkout_title": {"en": "Demo checkout", "kn": "ಡೆಮೊ ಚೆಕ್‌ಔಟ್", "hi": "डेमो चेकआउट"},
    "checkout_notice": {"en": "Demo only: no payment details collected, no card charged, no reservation made, no PNR issued.",
                        "kn": "ಡೆಮೊ ಮಾತ್ರ: ಪಾವತಿ ವಿವರ ಸಂಗ್ರಹಿಸಿಲ್ಲ, ಕಾರ್ಡ್ ಶುಲ್ಕವಿಲ್ಲ, ಕಾಯ್ದಿರಿಸುವಿಕೆ ಇಲ್ಲ, PNR ನೀಡಿಲ್ಲ.",
                        "hi": "केवल डेमो: कोई भुगतान जानकारी नहीं ली गई, कोई कार्ड चार्ज नहीं, कोई आरक्षण नहीं, कोई PNR नहीं।"},
    "checkout_status": {"en": "Demo complete · nothing booked", "kn": "ಡೆಮೊ ಪೂರ್ಣ · ಏನೂ ಬುಕ್ ಆಗಿಲ್ಲ", "hi": "डेमो पूरा · कुछ बुक नहीं हुआ"},
    "alert_badge": {"en": "Simulated update", "kn": "ಅನುಕರಣೆಯ ಅಪ್‌ಡೇಟ್", "hi": "सिम्युलेटेड अपडेट"},
    "alert_notice": {"en": "Demo only. No live airline feed is connected.", "kn": "ಡೆಮೊ ಮಾತ್ರ. ಯಾವುದೇ ಲೈವ್ ಏರ್‌ಲೈನ್ ಮಾಹಿತಿ ಸಂಪರ್ಕದಲ್ಲಿಲ್ಲ.",
                     "hi": "केवल डेमो। कोई लाइव एयरलाइन फ़ीड जुड़ी नहीं है।"},
    "departure": {"en": "Departure", "kn": "ಹೊರಡುವ ಸಮಯ", "hi": "प्रस्थान"},
    "delay": {"en": "{n} min delay", "kn": "{n} ನಿಮಿಷ ವಿಳಂಬ", "hi": "{n} मिनट देरी"},
    "day_n": {"en": "Day {n}", "kn": "ದಿನ {n}", "hi": "दिन {n}"},
    "route": {"en": "Route", "kn": "ಮಾರ್ಗ", "hi": "रूट"},
    "budget": {"en": "Indicative budget", "kn": "ಅಂದಾಜು ಬಜೆಟ್", "hi": "अनुमानित बजट"},
    "pp_day": {"en": "{amount} per person per day ({style})", "kn": "ಪ್ರತಿ ವ್ಯಕ್ತಿಗೆ ದಿನಕ್ಕೆ {amount} ({style})",
               "hi": "प्रति व्यक्ति प्रति दिन {amount} ({style})"},
    "plan_total": {"en": "{amount} for {n} traveller(s), excluding flights", "kn": "{n} ಪ್ರಯಾಣಿಕರಿಗೆ {amount}, ವಿಮಾನ ಹೊರತುಪಡಿಸಿ",
                   "hi": "{n} यात्री के लिए {amount}, फ़्लाइट छोड़कर"},
    "adjusted_badge": {"en": "Adjusted sample", "kn": "ಹೊಂದಿಸಿದ ಮಾದರಿ", "hi": "बदली गई सैंपल योजना"},
    "curated_badge": {"en": "Curated sample", "kn": "ಆಯ್ದ ಮಾದರಿ", "hi": "चुनी हुई सैंपल योजना"},
    "plan_disclaimer": {"en": "Timings and prices are indicative. Check opening hours and rates before you go.",
                        "kn": "ಸಮಯ ಮತ್ತು ಬೆಲೆಗಳು ಅಂದಾಜು. ಹೋಗುವ ಮೊದಲು ತೆರೆಯುವ ಸಮಯ ಮತ್ತು ದರಗಳನ್ನು ಪರಿಶೀಲಿಸಿ.",
                        "hi": "समय और कीमतें अनुमानित हैं। जाने से पहले खुलने का समय और दरें जाँच लें।"},
    "pick_date": {"en": "Pick a date", "kn": "ದಿನಾಂಕ ಆರಿಸಿ", "hi": "तारीख चुनें"},
    "confirm": {"en": "Use this date", "kn": "ಈ ದಿನಾಂಕ ಬಳಸಿ", "hi": "यह तारीख इस्तेमाल करें"},
    "or_type": {"en": "or just type it, e.g. “next Friday”", "kn": "ಅಥವಾ ಟೈಪ್ ಮಾಡಿ, ಉದಾ. “ಮುಂದಿನ ಶುಕ್ರವಾರ”",
                "hi": "या टाइप करें, जैसे “अगले शुक्रवार”"},
    "helpful": {"en": "Was this helpful?", "kn": "ಇದು ಸಹಾಯಕವಾಯಿತೇ?", "hi": "क्या यह मददगार था?"},
    "thanks_feedback": {"en": "Thanks for the feedback.", "kn": "ಪ್ರತಿಕ್ರಿಯೆಗೆ ಧನ್ಯವಾದಗಳು.", "hi": "प्रतिक्रिया के लिए धन्यवाद।"},
    "feedback_failed": {"en": "Feedback couldn't be saved.", "kn": "ಪ್ರತಿಕ್ರಿಯೆ ಉಳಿಸಲಾಗಲಿಲ್ಲ.", "hi": "प्रतिक्रिया सेव नहीं हो सकी।"},
    "source": {"en": "Source: Aura travel guide", "kn": "ಮೂಲ: ಔರಾ ಪ್ರಯಾಣ ಮಾರ್ಗದರ್ಶಿ", "hi": "स्रोत: ऑरा ट्रैवल गाइड"},
    "new_chat": {"en": "New chat", "kn": "ಹೊಸ ಚಾಟ್", "hi": "नई चैट"},
    "am_wifi": {"en": "Wi-Fi", "kn": "ವೈ-ಫೈ", "hi": "वाई-फ़ाई"},
    "am_pool": {"en": "Pool", "kn": "ಈಜುಕೊಳ", "hi": "पूल"},
    "am_breakfast": {"en": "Breakfast", "kn": "ಉಪಾಹಾರ", "hi": "नाश्ता"},
    "am_spa": {"en": "Spa", "kn": "ಸ್ಪಾ", "hi": "स्पा"},
    "am_gym": {"en": "Gym", "kn": "ಜಿಮ್", "hi": "जिम"},
    "am_shuttle": {"en": "Airport shuttle", "kn": "ವಿಮಾನ ನಿಲ್ದಾಣ ಶಟಲ್", "hi": "एयरपोर्ट शटल"},
    "am_beach": {"en": "Beach access", "kn": "ಕಡಲತೀರ ಪ್ರವೇಶ", "hi": "बीच तक पहुँच"},
    "am_kids": {"en": "Kids' club", "kn": "ಮಕ್ಕಳ ಕ್ಲಬ್", "hi": "किड्स क्लब"},
    "am_rooftop": {"en": "Rooftop", "kn": "ಮೇಲ್ಛಾವಣಿ", "hi": "रूफ़टॉप"},
    "am_parking": {"en": "Parking", "kn": "ಪಾರ್ಕಿಂಗ್", "hi": "पार्किंग"},
    "am_restaurant": {"en": "Restaurant", "kn": "ರೆಸ್ಟೋರೆಂಟ್", "hi": "रेस्टोरेंट"},
    "am_heritage": {"en": "Heritage property", "kn": "ಪಾರಂಪರಿಕ ಕಟ್ಟಡ", "hi": "हेरिटेज प्रॉपर्टी"},
    # seat page
    "seat_title": {"en": "Choose seats (demo)", "kn": "ಸೀಟು ಆರಿಸಿ (ಡೆಮೊ)", "hi": "सीट चुनें (डेमो)"},
    "seat_back": {"en": "← Back to chat", "kn": "← ಚಾಟ್‌ಗೆ ಹಿಂತಿರುಗಿ", "hi": "← चैट पर वापस"},
    "seat_save": {"en": "Save seats", "kn": "ಸೀಟು ಉಳಿಸಿ", "hi": "सीटें सेव करें"},
    "seat_skip": {"en": "Skip (assign at check-in)", "kn": "ಬಿಡಿ (ಚೆಕ್-ಇನ್‌ನಲ್ಲಿ ನಿಗದಿ)", "hi": "छोड़ें (चेक-इन पर तय)"},
    "seat_available": {"en": "Available", "kn": "ಲಭ್ಯ", "hi": "उपलब्ध"},
    "seat_extra": {"en": "Extra legroom", "kn": "ಹೆಚ್ಚು ಕಾಲುಜಾಗ", "hi": "ज़्यादा लेगरूम"},
    "seat_exit": {"en": "Exit row", "kn": "ತುರ್ತು ನಿರ್ಗಮನ ಸಾಲು", "hi": "एग्ज़िट रो"},
    "seat_occupied": {"en": "Taken", "kn": "ಭರ್ತಿ", "hi": "भरी हुई"},
    "seat_yours": {"en": "Your selection", "kn": "ನಿಮ್ಮ ಆಯ್ಕೆ", "hi": "आपकी पसंद"},
    "seat_free": {"en": "Free", "kn": "ಉಚಿತ", "hi": "मुफ़्त"},
    "seat_passenger": {"en": "Passenger {n}", "kn": "ಪ್ರಯಾಣಿಕ {n}", "hi": "यात्री {n}"},
    "seat_none": {"en": "No seat yet", "kn": "ಇನ್ನೂ ಸೀಟು ಇಲ್ಲ", "hi": "अभी सीट नहीं"},
    "seat_fees": {"en": "Seat fees (sample)", "kn": "ಸೀಟು ಶುಲ್ಕ (ಮಾದರಿ)", "hi": "सीट शुल्क (सैंपल)"},
}

_PH = re.compile(r"\{(\w+)\}")


def _pick(entry, lang, n):
    val = entry.get(lang) or entry.get("en")
    if isinstance(val, tuple):
        val = val[0] if n == 1 else val[1]
    if lang != "en" and not val:
        val = ""
    return val


def t(key: str, lang: str = "en", **kw) -> str:
    entry = M.get(key) or UI.get(key)
    if entry is None:
        return key
    val = _pick(entry, lang if lang in LANGS else "en", kw.get("n"))
    try:
        return val.format(**kw)
    except (KeyError, IndexError):
        return val


def ui_strings(lang: str) -> dict:
    lang = lang if lang in LANGS else "en"
    out = {}
    for k, entry in UI.items():
        v = entry.get(lang) or entry.get("en")
        out[k] = v[1] if isinstance(v, tuple) else v
    return out


def placeholders(s) -> set:
    if isinstance(s, tuple):
        return set().union(*(placeholders(x) for x in s))
    return set(_PH.findall(s or ""))


# Kannada / Hindi written in English letters (very common when typing on a phone).
# Strong markers alone are enough; weak ones need a second marker, because words like
# "se", "kal" or "ide" also occur in English or city names.
_KN_STRONG = {"beku", "bekagide", "beda", "naale", "nale", "nanage", "namaskara", "namaskaara", "illi",
              "alli", "elli", "yavaga", "eshtu", "hogbeku", "hogabeku", "barbeku", "maadi", "madi", "kodi",
              "gottilla", "houdu", "sari", "illa", "ide", "inda", "yenu", "enu", "naavu", "neevu",
              "naanu", "hegide", "chennagide", "dhanyavada", "dhanyavaadagalu", "ivattu", "nadiya"}
_KN_WEAK = {"ge", "ondu", "eradu", "mooru", "dina", "ooru", "hotelu", "flightu", "ticketu"}
_HI_STRONG = {"chahiye", "chaiye", "mujhe", "hamein", "humein", "kitna", "kitne", "kitni", "kyun", "kaise",
              "karo", "kijiye", "batao", "bataiye", "jaana", "jana", "hai", "hain", "nahi", "nahin",
              "namaste", "dhanyavaad", "shukriya", "parso", "kripya", "aap", "tum", "mera", "meri", "hum"}
_HI_WEAK = {"se", "tak", "kal", "ka", "ki", "ke", "ko", "log", "logon", "din", "raat", "wala", "wali"}


def _roman_lang(text: str) -> str | None:
    words = re.findall(r"[a-z]+", text.lower())
    if not words:
        return None
    kn = sum(2 for w in words if w in _KN_STRONG) + sum(1 for w in words if w in _KN_WEAK)
    hi = sum(2 for w in words if w in _HI_STRONG) + sum(1 for w in words if w in _HI_WEAK)
    if kn >= 2 and kn > hi:
        return "kn"
    if hi >= 3 and hi > kn:      # Hinglish needs a bit more evidence
        return "hi"
    return None


def detect_script_language(text: str) -> str | None:
    """Auto mode: Kannada/Devanagari script, or romanized Kannada/Hindi, switch the reply
    language; plain English text with several words switches back to English."""
    if re.search(r"[\u0C80-\u0CFF]", text):
        return "kn"
    if re.search(r"[\u0900-\u097F]", text):
        return "hi"
    roman = _roman_lang(text)
    if roman:
        return roman
    words = re.findall(r"[A-Za-z]+", text)
    if len(words) >= 3 and not re.search(r"[\u0B80-\u0D7F]", text):
        return "en"
    return None
