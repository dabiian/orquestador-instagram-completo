CURATED_CONTENT_MODES = {
    "phrase",
    "meme",
    "local_news",
    "world_news",
}

CONTENT_MODE_ALIASES = {
    "frase": "phrase",
    "frases": "phrase",
    "quote": "phrase",
    "quotes": "phrase",

    "meme": "meme",
    "memes": "meme",
    "humor": "meme",

    "noticia_local": "local_news",
    "noticias_locales": "local_news",
    "local": "local_news",
    "local_news": "local_news",

    "noticia_mundial": "world_news",
    "noticias_mundiales": "world_news",
    "global_news": "world_news",
    "world": "world_news",
    "world_news": "world_news",
}

AUTO_CONTENT_MODE_WEIGHTS = {
    "phrase": 30,
    "meme": 30,
    "local_news": 20,
    "world_news": 20,
}

CURATED_SOURCES = {
    "english": {
        "phrase": {
            "hashtags": [
                "dailyquotes",
                "quotesoftheday",
                "inspirationalquotes",
                "positivevibes",
                "mindset",
            ],
        },
        "meme": {
            "hashtags": [
                "memes",
                "relatablememes",
                "funny",
                "dailymemes",
                "memeoftheday",
            ],
        },
        "world_news": {
            "accounts": [
                "bbcnews",
                "reuters",
                "apnews",
                "cnn",
                "dwnews",
            ],
        },
        "local_news": {
            "locations": {
                "chicago": {
                    "accounts": [
                        "abc7chicago",
                        "nbcchicago",
                        "cbschicago",
                        "fox32chicago",
                        "blockclubchi",
                    ],
                },
                "miami": {
                    "accounts": [
                        "nbc6",
                        "wsvn",
                        "local10news",
                        "miamiherald",
                    ],
                },
                "new_york": {
                    "accounts": [
                        "ny1",
                        "nbcnewyork",
                        "abc7ny",
                        "cbsnewyork",
                    ],
                },
                "los_angeles": {
                    "accounts": [
                        "abc7la",
                        "nbcla",
                        "ktla5news",
                        "cbsla",
                    ],
                },
                "generic": {
                    "hashtags": [
                        "localnews",
                        "communitynews",
                        "citynews",
                    ],
                },
            },
        },
    },

    "spanish": {
        "phrase": {
            "hashtags": [
                "frases",
                "frasesdeldia",
                "reflexiones",
                "motivacion",
                "pensamientos",
            ],
        },
        "meme": {
            "hashtags": [
                "memesespañol",
                "humor",
                "memeslatinos",
                "risas",
                "humorlatino",
            ],
        },
        "world_news": {
            "accounts": [
                "bbcmundo",
                "cnnee",
                "dw_espanol",
                "el_pais",
                "rtve",
            ],
        },
        "local_news": {
            "locations": {
                "chicago": {
                    "accounts": [
                        "telemundochicago",
                        "univisionchicago",
                    ],
                },
                "miami": {
                    "accounts": [
                        "telemundo51",
                        "univision23",
                        "elnuevoherald",
                    ],
                },
                "new_york": {
                    "accounts": [
                        "univision41",
                        "telemundo47",
                    ],
                },
                "los_angeles": {
                    "accounts": [
                        "telemundo52",
                        "univision34",
                    ],
                },
                "generic": {
                    "hashtags": [
                        "noticiaslocales",
                        "noticiasdelacomunidad",
                        "noticiasciudad",
                    ],
                },
            },
        },
    },
}