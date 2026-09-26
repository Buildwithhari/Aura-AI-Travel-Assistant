# -*- coding: utf-8 -*-
"""
Location catalogue: airports, cities, states/UTs and aliases.

Design rules (see README "Locations"):
  * States, cities and airports are DIFFERENT things. A state never has one
    universal airport code; resolving a state returns the list of airports that
    serve it and the conversation asks the user to choose.
  * A city with more than one commonly used airport (Mumbai, Goa, London ...)
    is ambiguous: we return every option and ask, instead of guessing.
  * Every IATA code here is validated by tests/test_locations.py (format,
    uniqueness, every state/UT covered, every alias points at a real code).
  * Coordinates are approximate (city level) and are used ONLY to estimate
    sample flight durations and draw itinerary route sketches.

To extend: add an entry to AIRPORTS, then optionally add aliases in
CITY_ALIASES (alias -> list of codes) and the airport to STATES.
"""

from __future__ import annotations

import difflib
import re
from dataclasses import dataclass, field

# code: (airport name, city, state/UT or region, country, lat, lon)
AIRPORTS: dict[str, tuple[str, str, str, str, float, float]] = {
    # ---------------- India ----------------
    "VTZ": ("Visakhapatnam International", "Visakhapatnam", "Andhra Pradesh", "India", 17.72, 83.22),
    "VGA": ("Vijayawada International", "Vijayawada", "Andhra Pradesh", "India", 16.53, 80.80),
    "TIR": ("Tirupati Airport", "Tirupati", "Andhra Pradesh", "India", 13.63, 79.54),
    "RJA": ("Rajahmundry Airport", "Rajahmundry", "Andhra Pradesh", "India", 17.11, 81.82),
    "HGI": ("Donyi Polo Airport", "Itanagar", "Arunachal Pradesh", "India", 27.03, 93.73),
    "GAU": ("Lokpriya Gopinath Bordoloi International", "Guwahati", "Assam", "India", 26.11, 91.59),
    "DIB": ("Dibrugarh Airport", "Dibrugarh", "Assam", "India", 27.48, 95.02),
    "JRH": ("Jorhat Airport", "Jorhat", "Assam", "India", 26.73, 94.18),
    "IXS": ("Silchar Airport", "Silchar", "Assam", "India", 24.91, 92.98),
    "PAT": ("Jay Prakash Narayan Airport", "Patna", "Bihar", "India", 25.59, 85.09),
    "GAY": ("Gaya Airport", "Gaya", "Bihar", "India", 24.74, 84.95),
    "DBR": ("Darbhanga Airport", "Darbhanga", "Bihar", "India", 26.19, 85.91),
    "RPR": ("Swami Vivekananda Airport", "Raipur", "Chhattisgarh", "India", 21.18, 81.74),
    "GOI": ("Dabolim Airport", "Goa (Dabolim)", "Goa", "India", 15.38, 73.83),
    "GOX": ("Manohar International (Mopa)", "Goa (Mopa)", "Goa", "India", 15.73, 73.87),
    "AMD": ("Sardar Vallabhbhai Patel International", "Ahmedabad", "Gujarat", "India", 23.08, 72.63),
    "STV": ("Surat International", "Surat", "Gujarat", "India", 21.12, 72.74),
    "BDQ": ("Vadodara Airport", "Vadodara", "Gujarat", "India", 22.33, 73.22),
    "BHJ": ("Bhuj Airport", "Bhuj", "Gujarat", "India", 23.29, 69.67),
    "KUU": ("Kullu-Manali Airport (Bhuntar)", "Kullu", "Himachal Pradesh", "India", 31.88, 77.15),
    "DHM": ("Kangra Airport (Gaggal)", "Dharamshala", "Himachal Pradesh", "India", 32.17, 76.26),
    "SLV": ("Shimla Airport", "Shimla", "Himachal Pradesh", "India", 31.08, 77.07),
    "IXR": ("Birsa Munda Airport", "Ranchi", "Jharkhand", "India", 23.31, 85.32),
    "DGH": ("Deoghar Airport", "Deoghar", "Jharkhand", "India", 24.44, 86.70),
    "BLR": ("Kempegowda International", "Bengaluru", "Karnataka", "India", 13.20, 77.71),
    "IXE": ("Mangaluru International", "Mangaluru", "Karnataka", "India", 12.96, 74.89),
    "MYQ": ("Mysuru Airport", "Mysuru", "Karnataka", "India", 12.23, 76.66),
    "HBX": ("Hubballi Airport", "Hubballi", "Karnataka", "India", 15.36, 75.08),
    "IXG": ("Belagavi Airport", "Belagavi", "Karnataka", "India", 15.86, 74.62),
    "GBI": ("Kalaburagi Airport", "Kalaburagi", "Karnataka", "India", 17.31, 76.96),
    "COK": ("Cochin International", "Kochi", "Kerala", "India", 10.15, 76.40),
    "TRV": ("Thiruvananthapuram International", "Thiruvananthapuram", "Kerala", "India", 8.48, 76.92),
    "CCJ": ("Calicut International", "Kozhikode", "Kerala", "India", 11.14, 75.95),
    "CNN": ("Kannur International", "Kannur", "Kerala", "India", 11.92, 75.55),
    "IDR": ("Devi Ahilya Bai Holkar Airport", "Indore", "Madhya Pradesh", "India", 22.72, 75.80),
    "BHO": ("Raja Bhoj Airport", "Bhopal", "Madhya Pradesh", "India", 23.29, 77.34),
    "JLR": ("Jabalpur Airport", "Jabalpur", "Madhya Pradesh", "India", 23.18, 80.05),
    "GWL": ("Gwalior Airport", "Gwalior", "Madhya Pradesh", "India", 26.29, 78.23),
    "HJR": ("Khajuraho Airport", "Khajuraho", "Madhya Pradesh", "India", 24.82, 79.92),
    "BOM": ("Chhatrapati Shivaji Maharaj International", "Mumbai", "Maharashtra", "India", 19.09, 72.87),
    "NMI": ("Navi Mumbai International", "Navi Mumbai", "Maharashtra", "India", 18.99, 73.07),
    "PNQ": ("Pune Airport", "Pune", "Maharashtra", "India", 18.58, 73.92),
    "NAG": ("Dr. Babasaheb Ambedkar International", "Nagpur", "Maharashtra", "India", 21.09, 79.05),
    "IXU": ("Chhatrapati Sambhajinagar Airport", "Chhatrapati Sambhajinagar", "Maharashtra", "India", 19.86, 75.40),
    "KLH": ("Kolhapur Airport", "Kolhapur", "Maharashtra", "India", 16.66, 74.29),
    "IMF": ("Imphal International", "Imphal", "Manipur", "India", 24.76, 93.90),
    "SHL": ("Shillong Airport", "Shillong", "Meghalaya", "India", 25.70, 91.98),
    "AJL": ("Lengpui Airport", "Aizawl", "Mizoram", "India", 23.84, 92.62),
    "DMU": ("Dimapur Airport", "Dimapur", "Nagaland", "India", 25.88, 93.77),
    "BBI": ("Biju Patnaik International", "Bhubaneswar", "Odisha", "India", 20.24, 85.82),
    "JRG": ("Veer Surendra Sai Airport", "Jharsuguda", "Odisha", "India", 21.91, 84.05),
    "ATQ": ("Sri Guru Ram Dass Jee International", "Amritsar", "Punjab", "India", 31.71, 74.80),
    "JAI": ("Jaipur International", "Jaipur", "Rajasthan", "India", 26.82, 75.81),
    "UDR": ("Maharana Pratap Airport", "Udaipur", "Rajasthan", "India", 24.62, 73.90),
    "JDH": ("Jodhpur Airport", "Jodhpur", "Rajasthan", "India", 26.25, 73.05),
    "JSA": ("Jaisalmer Airport", "Jaisalmer", "Rajasthan", "India", 26.89, 70.86),
    "KQH": ("Kishangarh Airport", "Ajmer (Kishangarh)", "Rajasthan", "India", 26.60, 74.81),
    "PYG": ("Pakyong Airport", "Gangtok (Pakyong)", "Sikkim", "India", 27.23, 88.59),
    "MAA": ("Chennai International", "Chennai", "Tamil Nadu", "India", 12.99, 80.17),
    "CJB": ("Coimbatore International", "Coimbatore", "Tamil Nadu", "India", 11.03, 77.04),
    "IXM": ("Madurai Airport", "Madurai", "Tamil Nadu", "India", 9.83, 78.09),
    "TRZ": ("Tiruchirappalli International", "Tiruchirappalli", "Tamil Nadu", "India", 10.77, 78.71),
    "TCR": ("Thoothukudi Airport", "Thoothukudi", "Tamil Nadu", "India", 8.72, 78.03),
    "HYD": ("Rajiv Gandhi International", "Hyderabad", "Telangana", "India", 17.24, 78.43),
    "IXA": ("Maharaja Bir Bikram Airport", "Agartala", "Tripura", "India", 23.89, 91.24),
    "LKO": ("Chaudhary Charan Singh International", "Lucknow", "Uttar Pradesh", "India", 26.76, 80.88),
    "VNS": ("Lal Bahadur Shastri International", "Varanasi", "Uttar Pradesh", "India", 25.45, 82.86),
    "AYJ": ("Maharishi Valmiki International", "Ayodhya", "Uttar Pradesh", "India", 26.75, 82.15),
    "GOP": ("Gorakhpur Airport", "Gorakhpur", "Uttar Pradesh", "India", 26.74, 83.45),
    "IXD": ("Prayagraj Airport", "Prayagraj", "Uttar Pradesh", "India", 25.44, 81.73),
    "AGR": ("Agra Airport", "Agra", "Uttar Pradesh", "India", 27.16, 77.96),
    "DED": ("Jolly Grant Airport", "Dehradun", "Uttarakhand", "India", 30.19, 78.18),
    "PGH": ("Pantnagar Airport", "Pantnagar", "Uttarakhand", "India", 29.03, 79.47),
    "CCU": ("Netaji Subhas Chandra Bose International", "Kolkata", "West Bengal", "India", 22.65, 88.45),
    "IXB": ("Bagdogra International", "Siliguri (Bagdogra)", "West Bengal", "India", 26.68, 88.33),
    "RDP": ("Kazi Nazrul Islam Airport", "Durgapur", "West Bengal", "India", 23.62, 87.24),
    # Union Territories
    "IXZ": ("Veer Savarkar International", "Port Blair (Sri Vijaya Puram)", "Andaman and Nicobar Islands", "India", 11.64, 92.73),
    "IXC": ("Shaheed Bhagat Singh International", "Chandigarh", "Chandigarh", "India", 30.67, 76.79),
    "DIU": ("Diu Airport", "Diu", "Dadra and Nagar Haveli and Daman and Diu", "India", 20.71, 70.92),
    "DEL": ("Indira Gandhi International", "Delhi", "Delhi", "India", 28.56, 77.10),
    "SXR": ("Sheikh ul-Alam International", "Srinagar", "Jammu and Kashmir", "India", 33.99, 74.77),
    "IXJ": ("Jammu Airport", "Jammu", "Jammu and Kashmir", "India", 32.69, 74.84),
    "IXL": ("Kushok Bakula Rimpochee Airport", "Leh", "Ladakh", "India", 34.14, 77.55),
    "AGX": ("Agatti Aerodrome", "Agatti", "Lakshadweep", "India", 10.82, 72.18),
    "PNY": ("Puducherry Airport", "Puducherry", "Puducherry", "India", 11.97, 79.81),
    # ---------------- International (selected) ----------------
    "DXB": ("Dubai International", "Dubai", "Dubai", "United Arab Emirates", 25.25, 55.36),
    "DWC": ("Al Maktoum International", "Dubai (Al Maktoum)", "Dubai", "United Arab Emirates", 24.90, 55.16),
    "AUH": ("Zayed International", "Abu Dhabi", "Abu Dhabi", "United Arab Emirates", 24.43, 54.65),
    "SHJ": ("Sharjah International", "Sharjah", "Sharjah", "United Arab Emirates", 25.33, 55.52),
    "DOH": ("Hamad International", "Doha", "Doha", "Qatar", 25.27, 51.61),
    "MCT": ("Muscat International", "Muscat", "Muscat", "Oman", 23.59, 58.28),
    "SIN": ("Singapore Changi", "Singapore", "Singapore", "Singapore", 1.36, 103.99),
    "BKK": ("Suvarnabhumi Airport", "Bangkok", "Bangkok", "Thailand", 13.69, 100.75),
    "DMK": ("Don Mueang International", "Bangkok (Don Mueang)", "Bangkok", "Thailand", 13.91, 100.61),
    "HKT": ("Phuket International", "Phuket", "Phuket", "Thailand", 8.11, 98.31),
    "KUL": ("Kuala Lumpur International", "Kuala Lumpur", "Kuala Lumpur", "Malaysia", 2.74, 101.71),
    "DPS": ("I Gusti Ngurah Rai International", "Bali (Denpasar)", "Bali", "Indonesia", -8.75, 115.17),
    "CMB": ("Bandaranaike International", "Colombo", "Western Province", "Sri Lanka", 7.18, 79.88),
    "MLE": ("Velana International", "Male", "Kaafu", "Maldives", 4.19, 73.53),
    "KTM": ("Tribhuvan International", "Kathmandu", "Bagmati", "Nepal", 27.70, 85.36),
    "DAC": ("Hazrat Shahjalal International", "Dhaka", "Dhaka", "Bangladesh", 23.84, 90.40),
    "HKG": ("Hong Kong International", "Hong Kong", "Hong Kong", "Hong Kong SAR", 22.31, 113.91),
    "HND": ("Tokyo Haneda", "Tokyo (Haneda)", "Tokyo", "Japan", 35.55, 139.78),
    "NRT": ("Tokyo Narita", "Tokyo (Narita)", "Chiba", "Japan", 35.77, 140.39),
    "LHR": ("London Heathrow", "London (Heathrow)", "England", "United Kingdom", 51.47, -0.45),
    "LGW": ("London Gatwick", "London (Gatwick)", "England", "United Kingdom", 51.15, -0.19),
    "CDG": ("Paris Charles de Gaulle", "Paris (CDG)", "Ile-de-France", "France", 49.01, 2.55),
    "ORY": ("Paris Orly", "Paris (Orly)", "Ile-de-France", "France", 48.72, 2.38),
    "FRA": ("Frankfurt Airport", "Frankfurt", "Hesse", "Germany", 50.03, 8.56),
    "AMS": ("Amsterdam Schiphol", "Amsterdam", "North Holland", "Netherlands", 52.31, 4.76),
    "IST": ("Istanbul Airport", "Istanbul", "Istanbul", "Turkey", 41.26, 28.74),
    "JFK": ("John F. Kennedy International", "New York (JFK)", "New York", "United States", 40.64, -73.78),
    "EWR": ("Newark Liberty International", "New York (Newark)", "New Jersey", "United States", 40.69, -74.17),
    "SFO": ("San Francisco International", "San Francisco", "California", "United States", 37.62, -122.38),
    "YYZ": ("Toronto Pearson International", "Toronto", "Ontario", "Canada", 43.68, -79.63),
    "SYD": ("Sydney Kingsford Smith", "Sydney", "New South Wales", "Australia", -33.95, 151.18),
    "MEL": ("Melbourne Airport", "Melbourne", "Victoria", "Australia", -37.67, 144.84),
}

# State / UT -> airports that serve it. "gateway" marks airports physically in
# a neighbouring state/UT but commonly used (e.g. Haryana is served from DEL/IXC).
STATES: dict[str, dict] = {
    # 28 states
    "Andhra Pradesh": {"type": "state", "airports": ["VTZ", "VGA", "TIR", "RJA"]},
    "Arunachal Pradesh": {"type": "state", "airports": ["HGI"]},
    "Assam": {"type": "state", "airports": ["GAU", "DIB", "JRH", "IXS"]},
    "Bihar": {"type": "state", "airports": ["PAT", "GAY", "DBR"]},
    "Chhattisgarh": {"type": "state", "airports": ["RPR"]},
    "Goa": {"type": "state", "airports": ["GOI", "GOX"]},
    "Gujarat": {"type": "state", "airports": ["AMD", "STV", "BDQ", "BHJ"]},
    "Haryana": {"type": "state", "airports": [], "gateways": ["DEL", "IXC"]},
    "Himachal Pradesh": {"type": "state", "airports": ["KUU", "DHM", "SLV"]},
    "Jharkhand": {"type": "state", "airports": ["IXR", "DGH"]},
    "Karnataka": {"type": "state", "airports": ["BLR", "IXE", "MYQ", "HBX", "IXG", "GBI"]},
    "Kerala": {"type": "state", "airports": ["COK", "TRV", "CCJ", "CNN"]},
    "Madhya Pradesh": {"type": "state", "airports": ["IDR", "BHO", "JLR", "GWL", "HJR"]},
    "Maharashtra": {"type": "state", "airports": ["BOM", "NMI", "PNQ", "NAG", "IXU", "KLH"]},
    "Manipur": {"type": "state", "airports": ["IMF"]},
    "Meghalaya": {"type": "state", "airports": ["SHL"], "gateways": ["GAU"]},
    "Mizoram": {"type": "state", "airports": ["AJL"]},
    "Nagaland": {"type": "state", "airports": ["DMU"]},
    "Odisha": {"type": "state", "airports": ["BBI", "JRG"]},
    "Punjab": {"type": "state", "airports": ["ATQ"], "gateways": ["IXC"]},
    "Rajasthan": {"type": "state", "airports": ["JAI", "UDR", "JDH", "JSA", "KQH"]},
    "Sikkim": {"type": "state", "airports": ["PYG"], "gateways": ["IXB"]},
    "Tamil Nadu": {"type": "state", "airports": ["MAA", "CJB", "IXM", "TRZ", "TCR"]},
    "Telangana": {"type": "state", "airports": ["HYD"]},
    "Tripura": {"type": "state", "airports": ["IXA"]},
    "Uttar Pradesh": {"type": "state", "airports": ["LKO", "VNS", "AYJ", "GOP", "IXD", "AGR"]},
    "Uttarakhand": {"type": "state", "airports": ["DED", "PGH"]},
    "West Bengal": {"type": "state", "airports": ["CCU", "IXB", "RDP"]},
    # 8 union territories
    "Andaman and Nicobar Islands": {"type": "ut", "airports": ["IXZ"]},
    "Chandigarh": {"type": "ut", "airports": ["IXC"]},
    "Dadra and Nagar Haveli and Daman and Diu": {"type": "ut", "airports": ["DIU"]},
    "Delhi": {"type": "ut", "airports": ["DEL"]},
    "Jammu and Kashmir": {"type": "ut", "airports": ["SXR", "IXJ"]},
    "Ladakh": {"type": "ut", "airports": ["IXL"]},
    "Lakshadweep": {"type": "ut", "airports": ["AGX"]},
    "Puducherry": {"type": "ut", "airports": ["PNY"], "gateways": ["MAA"]},
}

STATE_ALIASES: dict[str, str] = {
    "andhra": "Andhra Pradesh", "andhra pradesh": "Andhra Pradesh", "ap": "Andhra Pradesh",
    "arunachal": "Arunachal Pradesh", "arunachal pradesh": "Arunachal Pradesh",
    "assam": "Assam", "bihar": "Bihar", "chhattisgarh": "Chhattisgarh", "chattisgarh": "Chhattisgarh",
    "gujarat": "Gujarat", "haryana": "Haryana",
    "himachal": "Himachal Pradesh", "himachal pradesh": "Himachal Pradesh",
    "jharkhand": "Jharkhand", "karnataka": "Karnataka", "kerala": "Kerala",
    "madhya pradesh": "Madhya Pradesh", "mp": "Madhya Pradesh",
    "maharashtra": "Maharashtra", "manipur": "Manipur", "meghalaya": "Meghalaya",
    "mizoram": "Mizoram", "nagaland": "Nagaland", "odisha": "Odisha", "orissa": "Odisha",
    "punjab": "Punjab", "rajasthan": "Rajasthan", "sikkim": "Sikkim",
    "tamil nadu": "Tamil Nadu", "tamilnadu": "Tamil Nadu", "tn": "Tamil Nadu",
    "telangana": "Telangana", "tripura": "Tripura",
    "uttar pradesh": "Uttar Pradesh", "up": "Uttar Pradesh",
    "uttarakhand": "Uttarakhand", "uttaranchal": "Uttarakhand",
    "west bengal": "West Bengal", "bengal": "West Bengal",
    "andaman": "Andaman and Nicobar Islands", "andaman and nicobar": "Andaman and Nicobar Islands",
    "andaman and nicobar islands": "Andaman and Nicobar Islands", "andamans": "Andaman and Nicobar Islands",
    "daman": "Dadra and Nagar Haveli and Daman and Diu", "dadra and nagar haveli": "Dadra and Nagar Haveli and Daman and Diu",
    "jammu and kashmir": "Jammu and Kashmir", "kashmir": "Jammu and Kashmir", "j&k": "Jammu and Kashmir",
    "ladakh": "Ladakh", "lakshadweep": "Lakshadweep",
    # Indic script
    "ಕರ್ನಾಟಕ": "Karnataka", "कर्नाटक": "Karnataka", "ಕೇರಳ": "Kerala", "केरल": "Kerala",
    "ರಾಜಸ್ಥಾನ": "Rajasthan", "राजस्थान": "Rajasthan", "ತಮಿಳುನಾಡು": "Tamil Nadu", "तमिलनाडु": "Tamil Nadu",
    "ಮಹಾರಾಷ್ಟ್ರ": "Maharashtra", "महाराष्ट्र": "Maharashtra",
}
# Keys that should NOT be matched inside running English text (too common as words).
_UNSAFE_SHORT = {"ap", "mp", "up", "tn", "man", "sin", "pat", "del", "can", "ams", "ist", "mel", "cok"}

# City / place alias -> codes. Cities without their own airport map to the
# airport(s) people normally use. More than one code == ambiguous -> ask.
CITY_ALIASES: dict[str, list[str]] = {
    # Karnataka
    "bengaluru": ["BLR"], "bangalore": ["BLR"], "banglore": ["BLR"], "bangaluru": ["BLR"],
    "bengalore": ["BLR"], "blore": ["BLR"], "kempegowda": ["BLR"],
    "ಬೆಂಗಳೂರು": ["BLR"], "ಬೆಂಗಳೂರ": ["BLR"], "बेंगलुरु": ["BLR"], "बेंगलुरू": ["BLR"], "बैंगलोर": ["BLR"],
    "mangaluru": ["IXE"], "mangalore": ["IXE"], "ಮಂಗಳೂರು": ["IXE"], "ಮಂಗಳೂರ": ["IXE"], "मंगलुरु": ["IXE"], "मंगलौर": ["IXE"],
    "mysuru": ["MYQ"], "mysore": ["MYQ"], "ಮೈಸೂರು": ["MYQ"], "ಮೈಸೂರ": ["MYQ"], "मैसूर": ["MYQ"],
    "hubballi": ["HBX"], "hubli": ["HBX"], "ಹುಬ್ಬಳ್ಳಿ": ["HBX"],
    "belagavi": ["IXG"], "belgaum": ["IXG"], "ಬೆಳಗಾವಿ": ["IXG"],
    "kalaburagi": ["GBI"], "gulbarga": ["GBI"],
    "coorg": ["IXE", "MYQ"], "kodagu": ["IXE", "MYQ"], "madikeri": ["IXE", "MYQ"],
    # Delhi NCR
    "delhi": ["DEL"], "new delhi": ["DEL"], "dilli": ["DEL"], "delhii": ["DEL"],
    "ದೆಹಲಿ": ["DEL"], "ದಿಲ್ಲಿ": ["DEL"], "दिल्ली": ["DEL"],
    "gurugram": ["DEL"], "gurgaon": ["DEL"], "noida": ["DEL"], "faridabad": ["DEL"], "ghaziabad": ["DEL"],
    # Maharashtra
    "mumbai": ["BOM", "NMI"], "bombay": ["BOM", "NMI"], "mumbay": ["BOM", "NMI"],
    "ಮುಂಬೈ": ["BOM", "NMI"], "ಮುಂಬಯಿ": ["BOM", "NMI"], "मुंबई": ["BOM", "NMI"],
    "navi mumbai": ["NMI"], "pune": ["PNQ"], "poona": ["PNQ"], "ಪುಣೆ": ["PNQ"], "पुणे": ["PNQ"],
    "nagpur": ["NAG"], "aurangabad": ["IXU"], "chhatrapati sambhajinagar": ["IXU"], "sambhajinagar": ["IXU"],
    "kolhapur": ["KLH"], "mahabaleshwar": ["PNQ"],
    # Tamil Nadu
    "chennai": ["MAA"], "madras": ["MAA"], "chenai": ["MAA"], "ಚೆನ್ನೈ": ["MAA"], "चेन्नई": ["MAA"],
    "coimbatore": ["CJB"], "kovai": ["CJB"], "ooty": ["CJB"], "madurai": ["IXM"], "rameswaram": ["IXM"],
    "kodaikanal": ["IXM"], "trichy": ["TRZ"], "tiruchirappalli": ["TRZ"],
    "thoothukudi": ["TCR"], "tuticorin": ["TCR"],
    # Telangana / AP
    "hyderabad": ["HYD"], "hydrabad": ["HYD"], "secunderabad": ["HYD"],
    "ಹೈದರಾಬಾದ್": ["HYD"], "ಹೈದರಾಬಾದ": ["HYD"], "हैदराबाद": ["HYD"],
    "visakhapatnam": ["VTZ"], "vizag": ["VTZ"], "vijayawada": ["VGA"], "tirupati": ["TIR"],
    "rajahmundry": ["RJA"], "rajamahendravaram": ["RJA"],
    # West Bengal / East / North-east
    "kolkata": ["CCU"], "calcutta": ["CCU"], "kolkatta": ["CCU"], "ಕೋಲ್ಕತ್ತಾ": ["CCU"], "ಕೊಲ್ಕತ್ತಾ": ["CCU"], "कोलकाता": ["CCU"],
    "siliguri": ["IXB"], "bagdogra": ["IXB"], "darjeeling": ["IXB"], "durgapur": ["RDP"],
    "gangtok": ["PYG", "IXB"], "pakyong": ["PYG"],
    "bhubaneswar": ["BBI"], "puri": ["BBI"], "jharsuguda": ["JRG"],
    "guwahati": ["GAU"], "dibrugarh": ["DIB"], "jorhat": ["JRH"], "kaziranga": ["JRH"], "silchar": ["IXS"],
    "itanagar": ["HGI"], "imphal": ["IMF"], "shillong": ["SHL"], "aizawl": ["AJL"], "dimapur": ["DMU"],
    "kohima": ["DMU"], "agartala": ["IXA"],
    "patna": ["PAT"], "पटना": ["PAT"], "gaya": ["GAY"], "bodh gaya": ["GAY"], "darbhanga": ["DBR"],
    "ranchi": ["IXR"], "deoghar": ["DGH"], "raipur": ["RPR"],
    # Goa (city-level alias for the state's two airports)
    "goa": ["GOI", "GOX"], "ಗೋವಾ": ["GOI", "GOX"], "गोवा": ["GOI", "GOX"],
    "dabolim": ["GOI"], "vasco": ["GOI"], "mopa": ["GOX"], "panaji": ["GOI", "GOX"],
    "मोपा": ["GOX"], "ಮೋಪಾ": ["GOX"], "डाबोलिम": ["GOI"], "दाबोलिम": ["GOI"], "ಡಾಬೋಲಿಮ್": ["GOI"],
    "नवी मुंबई": ["NMI"], "ನವಿ ಮುಂಬೈ": ["NMI"], "हीथ्रो": ["LHR"], "गैटविक": ["LGW"],
    # Gujarat
    "ahmedabad": ["AMD"], "ಅಹಮದಾಬಾದ್": ["AMD"], "अहमदाबाद": ["AMD"], "gandhinagar": ["AMD"],
    "surat": ["STV"], "vadodara": ["BDQ"], "baroda": ["BDQ"], "bhuj": ["BHJ"], "kutch": ["BHJ"],
    # Rajasthan
    "jaipur": ["JAI"], "ಜೈಪುರ": ["JAI"], "जयपुर": ["JAI"], "udaipur": ["UDR"], "ಉದಯಪುರ": ["UDR"], "उदयपुर": ["UDR"],
    "jodhpur": ["JDH"], "jaisalmer": ["JSA"], "ajmer": ["KQH"], "pushkar": ["KQH"], "kishangarh": ["KQH"],
    "mount abu": ["UDR"],
    # Kerala
    "kochi": ["COK"], "cochin": ["COK"], "ernakulam": ["COK"], "munnar": ["COK"],
    "alleppey": ["COK"], "alappuzha": ["COK"], "ಕೊಚ್ಚಿ": ["COK"], "कोच्चि": ["COK"],
    "thiruvananthapuram": ["TRV"], "trivandrum": ["TRV"], "trivandram": ["TRV"], "kovalam": ["TRV"],
    "ತಿರುವನಂತಪುರ": ["TRV"], "तिरुवनंतपुरम": ["TRV"], "kanyakumari": ["TRV"],
    "kozhikode": ["CCJ"], "calicut": ["CCJ"], "kannur": ["CNN"],
    # MP / UP / North
    "indore": ["IDR"], "bhopal": ["BHO"], "jabalpur": ["JLR"], "gwalior": ["GWL"], "khajuraho": ["HJR"],
    "lucknow": ["LKO"], "ಲಕ್ನೋ": ["LKO"], "लखनऊ": ["LKO"],
    "varanasi": ["VNS"], "banaras": ["VNS"], "benares": ["VNS"], "kashi": ["VNS"], "ವಾರಣಾಸಿ": ["VNS"], "वाराणसी": ["VNS"],
    "ayodhya": ["AYJ"], "gorakhpur": ["GOP"], "prayagraj": ["IXD"], "allahabad": ["IXD"], "agra": ["AGR"],
    "dehradun": ["DED"], "rishikesh": ["DED"], "haridwar": ["DED"], "mussoorie": ["DED"],
    "pantnagar": ["PGH"], "nainital": ["PGH"], "jim corbett": ["PGH"],
    "manali": ["KUU"], "kullu": ["KUU"], "dharamshala": ["DHM"], "mcleodganj": ["DHM"], "shimla": ["SLV"],
    "amritsar": ["ATQ"], "chandigarh": ["IXC"], "mohali": ["IXC"],
    "srinagar": ["SXR"], "श्रीनगर": ["SXR"], "gulmarg": ["SXR"], "pahalgam": ["SXR"], "jammu": ["IXJ"],
    "leh": ["IXL"],
    # UTs
    "port blair": ["IXZ"], "sri vijaya puram": ["IXZ"], "havelock": ["IXZ"],
    "agatti": ["AGX"], "diu": ["DIU"], "puducherry": ["PNY"], "pondicherry": ["PNY"], "pondy": ["PNY"],
    # International
    "dubai": ["DXB"], "ದುಬೈ": ["DXB"], "दुबई": ["DXB"], "al maktoum": ["DWC"],
    "abu dhabi": ["AUH"], "sharjah": ["SHJ"], "doha": ["DOH"], "qatar": ["DOH"], "muscat": ["MCT"],
    "singapore": ["SIN"], "ಸಿಂಗಾಪುರ": ["SIN"], "ಸಿಂಗಪುರ": ["SIN"], "सिंगापुर": ["SIN"],
    "bangkok": ["BKK", "DMK"], "ಬ್ಯಾಂಕಾಕ್": ["BKK", "DMK"], "बैंकॉक": ["BKK", "DMK"],
    "suvarnabhumi": ["BKK"], "don mueang": ["DMK"], "phuket": ["HKT"],
    "kuala lumpur": ["KUL"], "bali": ["DPS"], "denpasar": ["DPS"], "ಬಾಲಿ": ["DPS"], "बाली": ["DPS"],
    "colombo": ["CMB"], "maldives": ["MLE"], "kathmandu": ["KTM"], "dhaka": ["DAC"],
    "hong kong": ["HKG"], "tokyo": ["HND", "NRT"],
    "london": ["LHR", "LGW"], "ಲಂಡನ್": ["LHR", "LGW"], "लंदन": ["LHR", "LGW"], "heathrow": ["LHR"], "gatwick": ["LGW"],
    "paris": ["CDG", "ORY"], "ಪ್ಯಾರಿಸ್": ["CDG", "ORY"], "पेरिस": ["CDG", "ORY"],
    "frankfurt": ["FRA"], "amsterdam": ["AMS"], "istanbul": ["IST"],
    "new york": ["JFK", "EWR"], "nyc": ["JFK", "EWR"], "ನ್ಯೂಯಾರ್ಕ್": ["JFK", "EWR"], "न्यूयॉर्क": ["JFK", "EWR"],
    "newark": ["EWR"], "san francisco": ["SFO"], "toronto": ["YYZ"], "sydney": ["SYD"], "melbourne": ["MEL"],
}

INDIA = "India"

# Country -> airports to offer. India is deliberately empty: we ask for a city.
COUNTRY_ALIASES: dict[str, tuple[str, list[str]]] = {
    "india": ("India", []), "भारत": ("India", []), "ಭಾರತ": ("India", []),
    "uae": ("United Arab Emirates", ["DXB", "AUH", "SHJ"]), "united arab emirates": ("United Arab Emirates", ["DXB", "AUH", "SHJ"]),
    "emirates": ("United Arab Emirates", ["DXB", "AUH", "SHJ"]),
    "thailand": ("Thailand", ["BKK", "DMK", "HKT"]), "ಥೈಲ್ಯಾಂಡ್": ("Thailand", ["BKK", "DMK", "HKT"]), "थाईलैंड": ("Thailand", ["BKK", "DMK", "HKT"]),
    "uk": ("United Kingdom", ["LHR", "LGW"]), "united kingdom": ("United Kingdom", ["LHR", "LGW"]), "england": ("United Kingdom", ["LHR", "LGW"]),
    "usa": ("United States", ["JFK", "EWR", "SFO"]), "united states": ("United States", ["JFK", "EWR", "SFO"]), "america": ("United States", ["JFK", "EWR", "SFO"]),
    "japan": ("Japan", ["HND", "NRT"]), "france": ("France", ["CDG", "ORY"]), "malaysia": ("Malaysia", ["KUL"]),
    "indonesia": ("Indonesia", ["DPS"]), "sri lanka": ("Sri Lanka", ["CMB"]), "nepal": ("Nepal", ["KTM"]),
    "oman": ("Oman", ["MCT"]), "australia": ("Australia", ["SYD", "MEL"]), "canada": ("Canada", ["YYZ"]),
    "germany": ("Germany", ["FRA"]), "netherlands": ("Netherlands", ["AMS"]), "turkey": ("Turkey", ["IST"]),
    "bangladesh": ("Bangladesh", ["DAC"]),
}

# IANA time zone per country (and per-airport overrides) - used to show sample
# arrival times in the destination's local time, DST included.
COUNTRY_TZ = {
    "India": "Asia/Kolkata", "United Arab Emirates": "Asia/Dubai", "Qatar": "Asia/Qatar", "Oman": "Asia/Muscat",
    "Singapore": "Asia/Singapore", "Thailand": "Asia/Bangkok", "Malaysia": "Asia/Kuala_Lumpur",
    "Indonesia": "Asia/Makassar", "Sri Lanka": "Asia/Colombo", "Maldives": "Indian/Maldives",
    "Nepal": "Asia/Kathmandu", "Bangladesh": "Asia/Dhaka", "Hong Kong SAR": "Asia/Hong_Kong", "Japan": "Asia/Tokyo",
    "United Kingdom": "Europe/London", "France": "Europe/Paris", "Germany": "Europe/Berlin",
    "Netherlands": "Europe/Amsterdam", "Turkey": "Europe/Istanbul", "Canada": "America/Toronto",
    "Australia": "Australia/Sydney",
}
AIRPORT_TZ = {"JFK": "America/New_York", "EWR": "America/New_York", "SFO": "America/Los_Angeles",
              "MEL": "Australia/Melbourne"}


def tz_of(code: str) -> str:
    code = (code or "").upper()
    if code in AIRPORT_TZ:
        return AIRPORT_TZ[code]
    rec = AIRPORTS.get(code)
    return COUNTRY_TZ.get(rec[3], "Asia/Kolkata") if rec else "Asia/Kolkata"
_LATIN = re.compile(r"[a-z]")


@dataclass
class Place:
    """One matched place mention in a message."""
    text: str               # the matched surface text
    start: int
    end: int
    codes: list[str]        # candidate airport codes (1 = resolved, >1 = ambiguous)
    kind: str               # "airport" | "city" | "state"
    name: str               # canonical display name (city or state)
    is_code: bool = False
    note: str = ""          # e.g. "gateway airports" for states without their own
    extra: dict = field(default_factory=dict)


def airport(code: str) -> dict | None:
    """Airport record as a plain dict suitable for JSON/state."""
    code = (code or "").upper()
    rec = AIRPORTS.get(code)
    if not rec:
        return None
    name, city, region, country, lat, lon = rec
    return {"code": code, "name": name, "city": city, "region": region,
            "country": country, "lat": lat, "lon": lon}


def label(loc: dict | None) -> str:
    if not loc:
        return ""
    return f"{loc['city']} ({loc['code']})"


def is_domestic(*codes: str) -> bool:
    return all(AIRPORTS.get(c, ("", "", "", ""))[3] == INDIA for c in codes if c)


def state_airports(state: str) -> tuple[list[str], bool]:
    """Return (codes, uses_gateways)."""
    info = STATES.get(state) or {}
    own = list(info.get("airports", []))
    gw = [c for c in info.get("gateways", []) if c not in own]
    return own + gw, bool(gw) and not own


def _alias_table() -> list[tuple[str, str, list[str] | str]]:
    """(alias, kind, payload) sorted longest first so 'navi mumbai' beats 'mumbai'."""
    rows: list[tuple[str, str, list[str] | str]] = []
    for alias, codes in CITY_ALIASES.items():
        rows.append((alias, "city", codes))
    for alias, st in STATE_ALIASES.items():
        rows.append((alias, "state", st))
    for alias, ctry in COUNTRY_ALIASES.items():
        rows.append((alias, "country", ctry))
    rows.sort(key=lambda r: len(r[0]), reverse=True)
    return rows


_ALIASES = _alias_table()
_CODE_RE = re.compile(r"\b([A-Za-z]{3})\b")


def _is_indic(s: str) -> bool:
    return not _LATIN.search(s)


def find_places(text: str) -> list[Place]:
    """Find all place mentions, longest match first, non-overlapping, in order."""
    if not text:
        return []
    low = text.lower()
    taken = [False] * len(text)
    found: list[Place] = []

    def free(a: int, b: int) -> bool:
        return not any(taken[a:b])

    def claim(a: int, b: int) -> None:
        for i in range(a, b):
            taken[i] = True

    for alias, kind, payload in _ALIASES:
        if alias in _UNSAFE_SHORT:
            continue
        if _is_indic(alias):
            pattern = re.escape(alias)  # Indic scripts: allow inflection suffixes
        else:
            pattern = rf"(?<![a-z]){re.escape(alias)}(?![a-z])"
        for m in re.finditer(pattern, low):
            a, b = m.start(), m.end()
            if not free(a, b):
                continue
            claim(a, b)
            if kind == "city":
                codes = list(payload)  # type: ignore[arg-type]
                name = _display_city(alias, codes)
                found.append(Place(text[a:b], a, b, codes, "city", name))
            elif kind == "country":
                cname, codes = payload  # type: ignore[misc]
                found.append(Place(text[a:b], a, b, list(codes), "country", cname))
            else:
                st = payload  # type: ignore[assignment]
                codes, gw = state_airports(st)  # type: ignore[arg-type]
                found.append(Place(text[a:b], a, b, codes, "state", st,  # type: ignore[arg-type]
                                   note="gateway" if gw else ""))

    # Bare IATA codes: accept when written in capitals, when the whole message is
    # the code, or when used in a route ("blr to del", "del-bom").
    stripped = text.strip()
    for m in _CODE_RE.finditer(text):
        a, b = m.start(1), m.end(1)
        tok = m.group(1)
        up = tok.upper()
        if up not in AIRPORTS or not free(a, b):
            continue
        before = low[max(0, a - 6):a]
        after = low[b:b + 6]
        routeish = bool(re.search(r"(?:\bto|\bfrom|-|>|→)\s*$", before) or re.match(r"^\s*(?:to\b|-|>|→)", after))
        if tok.isupper() or stripped.lower() == tok.lower() or routeish:
            claim(a, b)
            ap = airport(up)
            found.append(Place(tok, a, b, [up], "airport", ap["city"], is_code=True))

    found.sort(key=lambda p: p.start)
    return found


def _display_city(alias: str, codes: list[str]) -> str:
    if len(codes) == 1:
        return AIRPORTS[codes[0]][1]
    # Ambiguous city: use a clean name.
    pretty = {
        "BOM": "Mumbai", "GOI": "Goa", "LHR": "London", "CDG": "Paris", "BKK": "Bangkok",
        "HND": "Tokyo", "JFK": "New York", "IXE": "Coorg", "PYG": "Gangtok",
    }
    return pretty.get(codes[0], alias.title())


def resolve_one(text: str) -> Place | None:
    places = find_places(text)
    return places[0] if places else None


def suggest(fragment: str, limit: int = 3) -> list[str]:
    """Close spelling matches (Latin script) -> airport codes to offer as 'did you mean'."""
    frag = (fragment or "").strip().lower()
    if len(frag) < 4 or not _LATIN.search(frag):
        return []
    keys = [k for k in CITY_ALIASES if _LATIN.search(k)]
    out: list[str] = []
    for word in re.findall(r"[a-z]{4,}", frag):
        for m in difflib.get_close_matches(word, keys, n=limit, cutoff=0.78):
            for c in CITY_ALIASES[m]:
                if c not in out:
                    out.append(c)
    return out[:limit]


def all_states() -> list[str]:
    return list(STATES)
