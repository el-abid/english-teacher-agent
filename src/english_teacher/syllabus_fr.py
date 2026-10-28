"""French syllabus, mirroring the English CEFR ladder.

Same rule as ``cefr.SYLLABUS``: static content, no model call. The tutor decides
*how* a topic is taught; this file decides *what* each level contains, so a
teacher can review it and the plan stays reproducible.
"""

from __future__ import annotations

from .cefr import Topic

FRENCH_SYLLABUS: dict[str, list[Topic]] = {
    "A1": [
        {
            "id": "FR-A1-1",
            "title": "Se présenter",
            "can_do": "Je peux saluer, dire mon nom, mon âge et ma nationalité.",
            "grammar": ["le verbe être", "les pronoms sujets", "les adjectifs possessifs"],
            "vocabulary": "salutations, nationalités, nombres 1-20, objets de classe",
        },
        {
            "id": "FR-A1-2",
            "title": "Ma famille et mes amis",
            "can_do": "Je peux présenter ma famille et décrire une personne.",
            "grammar": ["le verbe avoir", "le genre des noms", "l'accord des adjectifs"],
            "vocabulary": "famille, description physique, couleurs",
        },
        {
            "id": "FR-A1-3",
            "title": "La routine quotidienne",
            "can_do": "Je peux parler de ma journée et dire l'heure.",
            "grammar": [
                "le présent de l'indicatif",
                "les verbes pronominaux",
                "les adverbes de fréquence",
            ],
            "vocabulary": "heures, jours, activités quotidiennes",
        },
        {
            "id": "FR-A1-4",
            "title": "La nourriture et les courses",
            "can_do": "Je peux commander à manger et demander un prix.",
            "grammar": ["les articles partitifs", "combien de", "vouloir et pouvoir"],
            "vocabulary": "aliments, boissons, magasins, prix",
        },
        {
            "id": "FR-A1-5",
            "title": "En ville",
            "can_do": "Je peux demander et donner un itinéraire simple.",
            "grammar": ["il y a", "les prépositions de lieu", "l'impératif"],
            "vocabulary": "lieux, transports, directions",
        },
    ],
    "A2": [
        {
            "id": "FR-A2-1",
            "title": "Raconter au passé",
            "can_do": "Je peux raconter un week-end ou des vacances au passé.",
            "grammar": [
                "le passé composé avec avoir et être",
                "l'accord du participe passé",
                "les expressions de temps",
            ],
            "vocabulary": "vacances, voyages, sentiments",
        },
        {
            "id": "FR-A2-2",
            "title": "Projets et prévisions",
            "can_do": "Je peux parler de mes projets et faire des prévisions simples.",
            "grammar": ["le futur proche", "le futur simple", "si + présent"],
            "vocabulary": "projets, météo, rendez-vous",
        },
        {
            "id": "FR-A2-3",
            "title": "Comparer",
            "can_do": "Je peux comparer des personnes, des lieux et des produits.",
            "grammar": ["les comparatifs", "les superlatifs", "aussi ... que"],
            "vocabulary": "adjectifs de taille, de qualité, de prix",
        },
        {
            "id": "FR-A2-4",
            "title": "Santé et conseils",
            "can_do": "Je peux décrire un problème de santé et donner un conseil.",
            "grammar": ["l'impératif", "le verbe devoir", "il faut"],
            "vocabulary": "le corps, la maladie, le sport, les habitudes saines",
        },
        {
            "id": "FR-A2-5",
            "title": "Expériences vécues",
            "can_do": "Je peux parler d'expériences que j'ai déjà vécues.",
            "grammar": [
                "le passé composé avec déjà et jamais",
                "l'imparfait (introduction)",
            ],
            "vocabulary": "loisirs, réussites, souvenirs",
        },
    ],
    "B1": [
        {
            "id": "FR-B1-1",
            "title": "Récits et imparfait",
            "can_do": "Je peux raconter une anecdote en opposant décor et actions.",
            "grammar": [
                "l'imparfait et le passé composé",
                "les connecteurs temporels",
                "le plus-que-parfait (introduction)",
            ],
            "vocabulary": "souvenirs, anecdotes, émotions",
        },
        {
            "id": "FR-B1-2",
            "title": "Hypothèses et conséquences",
            "can_do": "Je peux expliquer ce qui se passera si une condition est remplie.",
            "grammar": ["si + présent + futur", "quand + futur", "les connecteurs de cause"],
            "vocabulary": "environnement, règles scolaires, conséquences",
        },
        {
            "id": "FR-B1-3",
            "title": "Donner son opinion",
            "can_do": "Je peux donner mon avis, approuver et désapprouver poliment.",
            "grammar": [
                "les verbes d'opinion + que",
                "les connecteurs logiques",
                "le subjonctif présent (introduction)",
            ],
            "vocabulary": "vie scolaire, technologie, temps libre",
        },
        {
            "id": "FR-B1-4",
            "title": "Décrire un processus",
            "can_do": "Je peux expliquer comment quelque chose est fabriqué ou réalisé.",
            "grammar": ["la voix passive", "les pronoms y et en", "les mots d'enchaînement"],
            "vocabulary": "fabrication, recettes, instructions",
        },
        {
            "id": "FR-B1-5",
            "title": "Raconter et réagir",
            "can_do": "Je peux raconter une histoire et réagir à celle d'un autre.",
            "grammar": [
                "le passé récent et le futur proche",
                "les verbes de réaction",
                "l'expression de la surprise",
            ],
            "vocabulary": "anecdotes, émotions, surprises",
        },
    ],
    "B2": [
        {
            "id": "FR-B2-1",
            "title": "Hypothèses irréelles",
            "can_do": "Je peux discuter de situations imaginaires et de leurs conséquences.",
            "grammar": ["le conditionnel présent", "si + imparfait", "j'aurais aimé"],
            "vocabulary": "ambitions, regrets, questions de société",
        },
        {
            "id": "FR-B2-2",
            "title": "Rapporter des propos",
            "can_do": "Je peux rapporter une conversation ou une nouvelle avec précision.",
            "grammar": [
                "le discours indirect",
                "la concordance des temps",
                "les verbes introducteurs",
            ],
            "vocabulary": "médias, interviews, annonces",
        },
        {
            "id": "FR-B2-3",
            "title": "Débattre d'un sujet",
            "can_do": "Je peux défendre une position et répondre à une objection.",
            "grammar": [
                "les connecteurs de concession",
                "le subjonctif après les conjonctions",
                "la modalisation",
            ],
            "vocabulary": "environnement, médias, politique éducative",
        },
        {
            "id": "FR-B2-4",
            "title": "Décrire et définir",
            "can_do": "Je peux définir et décrire une idée complexe avec précision.",
            "grammar": [
                "les propositions relatives",
                "le participe présent",
                "les nominalisations",
            ],
            "vocabulary": "sciences, culture, notions abstraites",
        },
        {
            "id": "FR-B2-5",
            "title": "Écrire un paragraphe argumenté",
            "can_do": "Je peux écrire un paragraphe structuré qui défend une thèse.",
            "grammar": [
                "les connecteurs formels",
                "la variété des phrases",
                "la reprise de l'information",
            ],
            "vocabulary": "verbes d'analyse, adjectifs d'évaluation",
        },
    ],
    "C1": [
        {
            "id": "FR-C1-1",
            "title": "Mise en relief et inversion",
            "can_do": "Je peux mettre en valeur une information avec des structures avancées.",
            "grammar": ["c'est ... qui / que", "l'inversion du sujet", "la dislocation"],
            "vocabulary": "rhétorique, journalisme, prise de parole",
        },
        {
            "id": "FR-C1-2",
            "title": "Spéculer sur le passé",
            "can_do": "Je peux formuler des hypothèses et des déductions sur le passé.",
            "grammar": [
                "le conditionnel passé",
                "si + plus-que-parfait",
                "les verbes de déduction",
            ],
            "vocabulary": "histoire, enquêtes, mystères",
        },
        {
            "id": "FR-C1-3",
            "title": "Nominalisation et registre",
            "can_do": "Je peux passer d'un registre oral à un registre académique.",
            "grammar": [
                "la nominalisation",
                "les constructions impersonnelles",
                "les groupes nominaux complexes",
            ],
            "vocabulary": "écrit académique, rapports, résumés",
        },
        {
            "id": "FR-C1-4",
            "title": "Nuancer l'argument",
            "can_do": "Je peux qualifier une thèse et anticiper les objections.",
            "grammar": ["la modalisation", "la concession", "les marqueurs discursifs"],
            "vocabulary": "éthique, technologie, débat public",
        },
        {
            "id": "FR-C1-5",
            "title": "Texte long et cohérent",
            "can_do": "Je peux écrire un essai cohérent de plusieurs paragraphes.",
            "grammar": [
                "l'architecture du paragraphe",
                "les chaînes de référence",
                "l'ellipse",
            ],
            "vocabulary": "phrase thématique, langage de la citation",
        },
    ],
    "C2": [
        {
            "id": "FR-C2-1",
            "title": "Connotation et précision",
            "can_do": "Je peux choisir le mot exact selon sa nuance de sens.",
            "grammar": ["les collocations", "les variations de registre", "l'euphémisme"],
            "vocabulary": "nuances de synonymes, connotations, figures de style",
        },
        {
            "id": "FR-C2-2",
            "title": "Fluidité idiomatique",
            "can_do": "Je peux employer des expressions idiomatiques avec naturel.",
            "grammar": [
                "les constructions idiomatiques",
                "les expressions figées",
                "la métaphore",
            ],
            "vocabulary": "idiotismes, proverbes, références culturelles",
        },
        {
            "id": "FR-C2-3",
            "title": "Lecture critique",
            "can_do": "Je peux repérer parti pris, présupposés et stratégie rhétorique.",
            "grammar": [
                "les adverbes de position",
                "l'ironie",
                "les questions rhétoriques",
            ],
            "vocabulary": "analyse du discours, esprit critique",
        },
        {
            "id": "FR-C2-4",
            "title": "Discours académique",
            "can_do": "Je peux soutenir une argumentation académique avec citations.",
            "grammar": ["le style nominal", "le passif de reporting", "la cohésion avancée"],
            "vocabulary": "écriture de recherche, évaluation, synthèse",
        },
        {
            "id": "FR-C2-5",
            "title": "Contrôle stylistique",
            "can_do": "Je peux adapter le ton et le style à différents publics.",
            "grammar": [
                "l'ellipse et la substitution",
                "l'ordre marqué des mots",
                "le parallélisme",
            ],
            "vocabulary": "style, voix, conscience du public",
        },
    ],
}
