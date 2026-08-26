"""ISO 3166-1 countries for checkout destination selection (not shipping prices)."""

# (code, name) — destination list only; never used as hardcoded shipping prices.
COUNTRIES = [
    ("AF", "Afghanistan"), ("AX", "Åland Islands"), ("AL", "Albania"), ("DZ", "Algeria"),
    ("AS", "American Samoa"), ("AD", "Andorra"), ("AO", "Angola"), ("AI", "Anguilla"),
    ("AQ", "Antarctica"), ("AG", "Antigua and Barbuda"), ("AR", "Argentina"), ("AM", "Armenia"),
    ("AW", "Aruba"), ("AU", "Australia"), ("AT", "Austria"), ("AZ", "Azerbaijan"),
    ("BS", "Bahamas"), ("BH", "Bahrain"), ("BD", "Bangladesh"), ("BB", "Barbados"),
    ("BY", "Belarus"), ("BE", "Belgium"), ("BZ", "Belize"), ("BJ", "Benin"),
    ("BM", "Bermuda"), ("BT", "Bhutan"), ("BO", "Bolivia"), ("BQ", "Bonaire, Sint Eustatius and Saba"),
    ("BA", "Bosnia and Herzegovina"), ("BW", "Botswana"), ("BV", "Bouvet Island"), ("BR", "Brazil"),
    ("IO", "British Indian Ocean Territory"), ("BN", "Brunei"), ("BG", "Bulgaria"), ("BF", "Burkina Faso"),
    ("BI", "Burundi"), ("CV", "Cabo Verde"), ("KH", "Cambodia"), ("CM", "Cameroon"),
    ("CA", "Canada"), ("KY", "Cayman Islands"), ("CF", "Central African Republic"), ("TD", "Chad"),
    ("CL", "Chile"), ("CN", "China"), ("CX", "Christmas Island"), ("CC", "Cocos (Keeling) Islands"),
    ("CO", "Colombia"), ("KM", "Comoros"), ("CG", "Congo"), ("CD", "Congo (DRC)"),
    ("CK", "Cook Islands"), ("CR", "Costa Rica"), ("CI", "Côte d'Ivoire"), ("HR", "Croatia"),
    ("CU", "Cuba"), ("CW", "Curaçao"), ("CY", "Cyprus"), ("CZ", "Czechia"),
    ("DK", "Denmark"), ("DJ", "Djibouti"), ("DM", "Dominica"), ("DO", "Dominican Republic"),
    ("EC", "Ecuador"), ("EG", "Egypt"), ("SV", "El Salvador"), ("GQ", "Equatorial Guinea"),
    ("ER", "Eritrea"), ("EE", "Estonia"), ("SZ", "Eswatini"), ("ET", "Ethiopia"),
    ("FK", "Falkland Islands"), ("FO", "Faroe Islands"), ("FJ", "Fiji"), ("FI", "Finland"),
    ("FR", "France"), ("GF", "French Guiana"), ("PF", "French Polynesia"), ("TF", "French Southern Territories"),
    ("GA", "Gabon"), ("GM", "Gambia"), ("GE", "Georgia"), ("DE", "Germany"),
    ("GH", "Ghana"), ("GI", "Gibraltar"), ("GR", "Greece"), ("GL", "Greenland"),
    ("GD", "Grenada"), ("GP", "Guadeloupe"), ("GU", "Guam"), ("GT", "Guatemala"),
    ("GG", "Guernsey"), ("GN", "Guinea"), ("GW", "Guinea-Bissau"), ("GY", "Guyana"),
    ("HT", "Haiti"), ("HM", "Heard Island and McDonald Islands"), ("VA", "Vatican City"),
    ("HN", "Honduras"), ("HK", "Hong Kong"), ("HU", "Hungary"), ("IS", "Iceland"),
    ("IN", "India"), ("ID", "Indonesia"), ("IR", "Iran"), ("IQ", "Iraq"),
    ("IE", "Ireland"), ("IM", "Isle of Man"), ("IL", "Israel"), ("IT", "Italy"),
    ("JM", "Jamaica"), ("JP", "Japan"), ("JE", "Jersey"), ("JO", "Jordan"),
    ("KZ", "Kazakhstan"), ("KE", "Kenya"), ("KI", "Kiribati"), ("KP", "North Korea"),
    ("KR", "South Korea"), ("KW", "Kuwait"), ("KG", "Kyrgyzstan"), ("LA", "Laos"),
    ("LV", "Latvia"), ("LB", "Lebanon"), ("LS", "Lesotho"), ("LR", "Liberia"),
    ("LY", "Libya"), ("LI", "Liechtenstein"), ("LT", "Lithuania"), ("LU", "Luxembourg"),
    ("MO", "Macao"), ("MG", "Madagascar"), ("MW", "Malawi"), ("MY", "Malaysia"),
    ("MV", "Maldives"), ("ML", "Mali"), ("MT", "Malta"), ("MH", "Marshall Islands"),
    ("MQ", "Martinique"), ("MR", "Mauritania"), ("MU", "Mauritius"), ("YT", "Mayotte"),
    ("MX", "Mexico"), ("FM", "Micronesia"), ("MD", "Moldova"), ("MC", "Monaco"),
    ("MN", "Mongolia"), ("ME", "Montenegro"), ("MS", "Montserrat"), ("MA", "Morocco"),
    ("MZ", "Mozambique"), ("MM", "Myanmar"), ("NA", "Namibia"), ("NR", "Nauru"),
    ("NP", "Nepal"), ("NL", "Netherlands"), ("NC", "New Caledonia"), ("NZ", "New Zealand"),
    ("NI", "Nicaragua"), ("NE", "Niger"), ("NG", "Nigeria"), ("NU", "Niue"),
    ("NF", "Norfolk Island"), ("MK", "North Macedonia"), ("MP", "Northern Mariana Islands"),
    ("NO", "Norway"), ("OM", "Oman"), ("PK", "Pakistan"), ("PW", "Palau"),
    ("PS", "Palestine"), ("PA", "Panama"), ("PG", "Papua New Guinea"), ("PY", "Paraguay"),
    ("PE", "Peru"), ("PH", "Philippines"), ("PN", "Pitcairn"), ("PL", "Poland"),
    ("PT", "Portugal"), ("PR", "Puerto Rico"), ("QA", "Qatar"), ("RE", "Réunion"),
    ("RO", "Romania"), ("RU", "Russia"), ("RW", "Rwanda"), ("BL", "Saint Barthélemy"),
    ("SH", "Saint Helena"), ("KN", "Saint Kitts and Nevis"), ("LC", "Saint Lucia"),
    ("MF", "Saint Martin"), ("PM", "Saint Pierre and Miquelon"),
    ("VC", "Saint Vincent and the Grenadines"), ("WS", "Samoa"), ("SM", "San Marino"),
    ("ST", "Sao Tome and Principe"), ("SA", "Saudi Arabia"), ("SN", "Senegal"),
    ("RS", "Serbia"), ("SC", "Seychelles"), ("SL", "Sierra Leone"), ("SG", "Singapore"),
    ("SX", "Sint Maarten"), ("SK", "Slovakia"), ("SI", "Slovenia"), ("SB", "Solomon Islands"),
    ("SO", "Somalia"), ("ZA", "South Africa"), ("GS", "South Georgia and the South Sandwich Islands"),
    ("SS", "South Sudan"), ("ES", "Spain"), ("LK", "Sri Lanka"), ("SD", "Sudan"),
    ("SR", "Suriname"), ("SJ", "Svalbard and Jan Mayen"), ("SE", "Sweden"), ("CH", "Switzerland"),
    ("SY", "Syria"), ("TW", "Taiwan"), ("TJ", "Tajikistan"), ("TZ", "Tanzania"),
    ("TH", "Thailand"), ("TL", "Timor-Leste"), ("TG", "Togo"), ("TK", "Tokelau"),
    ("TO", "Tonga"), ("TT", "Trinidad and Tobago"), ("TN", "Tunisia"), ("TR", "Turkey"),
    ("TM", "Turkmenistan"), ("TC", "Turks and Caicos Islands"), ("TV", "Tuvalu"),
    ("UG", "Uganda"), ("UA", "Ukraine"), ("AE", "United Arab Emirates"),
    ("GB", "United Kingdom"), ("US", "United States"),
    ("UM", "United States Minor Outlying Islands"), ("UY", "Uruguay"), ("UZ", "Uzbekistan"),
    ("VU", "Vanuatu"), ("VE", "Venezuela"), ("VN", "Vietnam"),
    ("VG", "British Virgin Islands"), ("VI", "U.S. Virgin Islands"),
    ("WF", "Wallis and Futuna"), ("EH", "Western Sahara"), ("YE", "Yemen"),
    ("ZM", "Zambia"), ("ZW", "Zimbabwe"), ("XK", "Kosovo"),
]


def country_options():
    rows = [{"code": code, "name": name} for code, name in COUNTRIES]
    rows.sort(key=lambda row: row["name"].casefold())
    return rows


def resolve_country(value):
    """Return (code, name) from a code or country name."""
    raw = (value or "").strip()
    if not raw:
        return None, None
    upper = raw.upper()
    for code, name in COUNTRIES:
        if upper == code or raw.lower() == name.lower():
            return code, name
    if "gambia" in raw.lower():
        return "GM", "Gambia"
    if raw.lower() in ("uk", "great britain", "britain", "england"):
        return "GB", "United Kingdom"
    if raw.lower() in ("usa", "america", "united states of america"):
        return "US", "United States"
    if "ivoire" in raw.lower() or "ivory" in raw.lower():
        return "CI", "Côte d'Ivoire"
    for code, name in COUNTRIES:
        if raw.lower() in name.lower() or name.lower() in raw.lower():
            return code, name
    return None, None
