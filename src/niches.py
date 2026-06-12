"""
Nisjedefinisjoner og nøkkelordliste fra Discovery Spec seksjon 5.

20 nisjer fordelt på 4 kategorier:
  HELSE        — weightloss, strength_training, nutrition, mental_health, sleep
  ØKONOMI      — personal_finance, investing, side_hustle, freelancer, creator_business
  RELASJONER   — dating_men, dating_women, marriage, social_skills, masculinity, femininity
  MINDSET      — productivity, morning_routine, confidence, stoicism

Matchingregel (seksjon 5):
  1 sterkt nøkkelord  →  treff
  4+ svake nøkkelord fra SAMME nisje  →  treff
"""

NICHES: dict[str, dict[str, list[str]]] = {
    # ----- HELSE -----
    "weightloss": {
        "strong": [
            "weightloss", "fatloss", "weightlosstransformation", "caloriedeficit",
            "fattofit", "weightlossjourney", "weightlosscheck", "fatlossjourney",
            "loseweight", "fatlosstips", "weightlosstips", "bodyrecomposition",
            "beforeandafter", "losingweight",
        ],
        "weak": ["transformation", "diet", "fitness", "healthy"],
    },
    "strength_training": {
        "strong": [
            "bodytransformation", "musclegain", "strengthtraining", "bodybuilding",
            "gymtok", "powerlifting", "hypertrophy", "musclebuilding", "weightlifting",
            "shredded", "bulking", "gains", "legday", "gymrat", "physique",
            "workoutroutine", "buildmuscle",
        ],
        "weak": ["gym", "workout", "gymlife", "fit"],
    },
    "nutrition": {
        "strong": [
            "nutrition", "mealprep", "cleaneating", "nutritioncoach", "macros",
            "mealplanning", "highprotein", "nutritionist", "mealprepideas",
            "foodismedicine", "nutritiontips", "dietitian", "healthyrecipes",
            "eatclean", "proteinintake",
        ],
        "weak": ["healthyfood", "diet", "protein", "food"],
    },
    "mental_health": {
        "strong": [
            "mentalhealth", "mentalhealthawareness", "anxietyrelief", "anxietysupport",
            "socialanxiety", "stressrelief", "mentalhealthjourney", "mentalhealthmatters",
            "overthinking", "burnout", "therapyworks", "mentalwellness",
            "endthestigma", "depressionhelp",
        ],
        "weak": ["healing", "therapy", "wellness", "mindfulness"],
    },
    "sleep": {
        "strong": [
            "sleeptips", "bettersleep", "sleephealth", "sleephygiene", "insomniatips",
            "sleepbetter", "sleepscience", "qualitysleep", "sleepdisorder",
            "restfulsleep", "sleepcoach", "recoverycoach", "sleepoptimization",
        ],
        "weak": ["sleep", "rest", "insomnia", "recovery"],
    },
    # ----- ØKONOMI -----
    "personal_finance": {
        "strong": [
            "personalfinance", "budgeting", "debtfree", "financialliteracy",
            "debtfreejourney", "savingmoney", "moneytips", "moneymanagement",
            "financialeducation", "debtfreecommunity", "budgetingtips", "frugalliving",
            "debtpayoff", "financetips", "moneymindset", "financetok",
        ],
        "weak": ["money", "finance", "savings", "wealth"],
    },
    "investing": {
        "strong": [
            "investing", "stockmarket", "realestateinvesting", "investingtips",
            "dividends", "wealthbuilding", "passiveincome", "cryptoinvesting",
            "indexfunds", "investingforbeginners", "stockmarketinvesting",
            "financialindependence", "retirementplanning", "passiveincomestreams",
        ],
        "weak": ["crypto", "stocks", "investor", "bitcoin"],
    },
    "side_hustle": {
        "strong": [
            "sidehustle", "sideincome", "makemoneyonline", "extraincome",
            "onlinebusiness", "sidegigs", "sidehustleideas", "multipleincome",
            "incomestreams", "digitalproducts", "affiliatemarketing",
        ],
        "weak": ["workfromhome", "entrepreneur", "hustle"],
    },
    "freelancer": {
        "strong": [
            "freelancer", "freelancing", "solopreneur", "remotework", "digitalnomad",
            "clientwork", "freelancetips", "solopreneurlife", "workfromanywhere",
            "consultingbusiness", "beyourownboss", "buildabusiness",
        ],
        "weak": ["onlinebusiness", "startup", "entrepreneur"],
    },
    "creator_business": {
        "strong": [
            "contentcreator", "creatorbusiness", "creatoreconomy", "contentcreatortips",
            "ugccreator", "branddeals", "creatorcoach", "monetize", "buildanaudience",
            "instagramgrowth", "tiktokgrowth", "growyourbrand", "socialmediagrowth",
            "creatorstrategy", "ugc", "socialmediacoach",
        ],
        "weak": ["contentmarketing", "socialmedia", "digitalmarketing"],
    },
    # ----- RELASJONER -----
    "dating_men": {
        "strong": [
            "datingadvice", "datingformen", "datingcoachformen", "attractionadvice",
            "howtoattractwomen", "masculinity", "redpill", "textinggirls",
            "datingtips", "alphamale", "datingcoach", "datingadviceformen",
        ],
        "weak": ["dating", "singlelife", "relationships"],
    },
    "dating_women": {
        "strong": [
            "datingadvice", "datingforwomen", "datingadviceforwomen", "attractingmen",
            "datingcoachforwomen", "modernloving", "greenflags", "redflagsinrelationships",
            "highvaluewoman", "situationships",
        ],
        "weak": ["dating", "singlelife", "selflove"],
    },
    "marriage": {
        "strong": [
            "marriageadvice", "marriagetips", "relationshipadvice", "healthyrelationship",
            "communicationinrelationships", "strongmarriage", "relationshipcoach",
            "couplegoals", "relationshiptips", "relationshipgoals", "loveadvice",
            "relationshipexpert",
        ],
        "weak": ["marriage", "relationship", "love", "couple"],
    },
    "social_skills": {
        "strong": [
            "socialskills", "socialanxiety", "charisma", "socialdynamics",
            "confidencebuilding", "howtobeconfident", "communication", "publicspeaking",
            "introvert", "socialconfidence", "socialintelligence",
        ],
        "weak": ["confidence", "networking", "selfimprovement"],
    },
    "masculinity": {
        "strong": [
            "masculinity", "manhood", "masculineenergy", "beaman", "mensmentalhealth",
            "menscoach", "brotherhood", "sigmamale", "gentlemans", "menhelpingmen",
            "empoweringmen", "menshealth", "fatherhood",
        ],
        "weak": ["men", "alpha", "selfimprovement", "stoic"],
    },
    "femininity": {
        "strong": [
            "femininity", "feminineenergy", "womanhood", "softlife", "highvaluewoman",
            "femininelifestyle", "femininecoach", "sacredfeminine", "goddesslifestyle",
            "womensempowerment", "softersideoflife", "divinefeminine",
        ],
        "weak": ["selflove", "women", "empowerment"],
    },
    # ----- MINDSET / SELVUTVIKLING -----
    "productivity": {
        "strong": [
            "productivity", "discipline", "productivitytips", "timemanagement",
            "deepwork", "habitbuilding", "productivityhacks", "goalsetting",
            "dailyhabits", "consistencyiskey", "focusmode", "getthingsdone",
            "timeblocking",
        ],
        "weak": ["success", "mindset", "goals", "hustle"],
    },
    "morning_routine": {
        "strong": [
            "morningroutine", "morningmotivation", "dailyroutine", "5amclub",
            "morningrituals", "successhabits", "routinecheck", "wakeupearlyclub",
            "morninghabits", "dailyroutinecheck", "lifestyledesign",
        ],
        "weak": ["lifestyle", "routine", "habits", "wellness"],
    },
    "confidence": {
        "strong": [
            "selfconfidence", "confidencebuilding", "buildconfidence", "confidentmindset",
            "selftrust", "selfworth", "overcomeselfdoubt", "socialconfidence",
            "becomeyourbestself", "mindsetshift",
        ],
        "weak": ["confidence", "selflove", "growthmindset", "believe"],
    },
    "stoicism": {
        "strong": [
            "stoicism", "stoic", "stoicmindset", "marcusaurelius", "dailystoic",
            "stoicwisdom", "stoicphilosophy", "epictetus", "seneca", "stoiclife",
            "stoicismdaily", "philosophyoflife", "ancientwisdom", "modernstoic",
        ],
        "weak": ["philosophy", "wisdom", "discipline", "mindset"],
    },
}


def _normalize_tokens(text: str) -> set[str]:
    out: set[str] = set()
    current = []
    for ch in text.lower():
        if ch.isalnum():
            current.append(ch)
        else:
            if current:
                out.add("".join(current))
                current = []
    if current:
        out.add("".join(current))
    return out


def match_niche(text: str) -> str | None:
    """Returner navnet på første matchende nisje, eller None.

    Regel (spec seksjon 5):
      - 1 sterkt nøkkelord  →  treff
      - 4+ svake nøkkelord fra SAMME nisje  →  treff
    Sterkt veier alltid før svakt. Første match i NICHES-rekkefølge vinner ved like.
    """
    tokens = _normalize_tokens(text)

    for niche, kw in NICHES.items():
        if any(strong in tokens for strong in kw["strong"]):
            return niche

    for niche, kw in NICHES.items():
        weak_hits = sum(1 for w in kw["weak"] if w in tokens)
        if weak_hits >= 4:
            return niche

    return None
