# ruff: noqa: E501  (prose: one paragraph per line)
"""Long descriptions of the demo pieces (English and French).

Format read by the Svelte ``ScoreDetails`` view: ``## `` starts a section,
``- `` a list item, blank lines separate paragraphs, URLs become links.
Every fact here comes from the sources listed under each piece; keep it that way
when editing (and keep both languages saying the same thing).
"""

from inspect import cleandoc

WIKI = "https://en.wikipedia.org/wiki"

BACH_846 = cleandoc(f"""
    ## History
    This prelude opens Book I of The Well-Tempered Clavier, 24 preludes and fugues in every major and minor key. Bach's autograph title page is dated 1722 and says the collection is meant "for the profit and use of musical youth desirous of learning", and as a pastime for those already skilled. "Well-tempered" refers to a tuning in which all keys can be played.

    An earlier, shorter version (BWV 846a) is in the Klavierbüchlein that Bach began in 1720 for his eldest son, Wilhelm Friedemann. The final prelude is 35 bars of broken chords: each bar spells out one harmony, played twice, and the piece ends over long pedal notes on G and then C.

    ## Playing it
    - Play each bar as a block chord first. You will hear the harmonic journey, and the fingering becomes obvious.
    - Hold the left-hand notes for their full written length: they make the resonance, so you need little pedal.
    - Keep the pulse perfectly even and shape the dynamics over several bars, towards the tense chords over the G in the bass near the end.
    - Count your bars: some 19th-century editions add an extra bar between bars 22 and 23 (the "Schwencke bar"). Bach's text has 35.

    ## Did you know?
    Charles Gounod improvised a melody over this prelude; his future father-in-law, Pierre-Joseph-Guillaume Zimmerman, wrote it down. It was published in 1853 as a "Méditation", and in 1859 with the Latin text that made it famous as the Bach–Gounod "Ave Maria". Gounod's edition includes the extra Schwencke bar.

    ## Sources
    - Wikipedia, "Prelude and Fugue in C major, BWV 846": {WIKI}/Prelude_and_Fugue_in_C_major,_BWV_846
    - Wikipedia, "The Well-Tempered Clavier": {WIKI}/The_Well-Tempered_Clavier
    - Wikipedia, "Ave Maria (Bach/Gounod)": {WIKI}/Ave_Maria_(Bach/Gounod)
""")

BACH_846_FR = cleandoc(f"""
    ## Histoire
    Ce prélude ouvre le premier livre du Clavier bien tempéré : 24 préludes et fugues dans toutes les tonalités majeures et mineures. La page de titre autographe de Bach est datée de 1722 ; le recueil y est destiné « à l'usage et au profit de la jeunesse musicienne désireuse d'apprendre », et au divertissement de ceux qui sont déjà habiles. « Bien tempéré » désigne un accord de l'instrument qui permet de jouer dans toutes les tonalités.

    Une version antérieure, plus courte (BWV 846a), figure dans le Klavierbüchlein que Bach commença en 1720 pour son fils aîné, Wilhelm Friedemann. Le prélude définitif compte 35 mesures d'accords brisés : chaque mesure déploie une harmonie, jouée deux fois, et la pièce se termine sur de longues pédales de sol puis de do.

    ## Conseils de jeu
    - Jouez d'abord chaque mesure en accord plaqué : vous entendrez le parcours harmonique, et le doigté s'impose de lui-même.
    - Tenez les notes de la main gauche sur toute leur durée écrite : ce sont elles qui font résonner, il faut donc peu de pédale.
    - Gardez une pulsation parfaitement égale et construisez les nuances sur plusieurs mesures, vers les accords tendus sur la basse de sol, à la fin.
    - Comptez vos mesures : certaines éditions du XIXe siècle ajoutent une mesure entre les mesures 22 et 23 (la « mesure de Schwencke »). Le texte de Bach en compte 35.

    ## Le saviez-vous ?
    Charles Gounod improvisa une mélodie sur ce prélude ; son futur beau-père, Pierre-Joseph-Guillaume Zimmerman, la nota. Elle parut en 1853 sous le titre de « Méditation », puis en 1859 avec le texte latin qui l'a rendue célèbre : l'« Ave Maria » de Bach-Gounod. L'édition de Gounod contient la mesure ajoutée de Schwencke.

    ## Sources
    - Wikipédia (en), « Prelude and Fugue in C major, BWV 846 » : {WIKI}/Prelude_and_Fugue_in_C_major,_BWV_846
    - Wikipédia (en), « The Well-Tempered Clavier » : {WIKI}/The_Well-Tempered_Clavier
    - Wikipédia (en), « Ave Maria (Bach/Gounod) » : {WIKI}/Ave_Maria_(Bach/Gounod)
""")

ELISE = cleandoc(f"""
    ## History
    Für Elise is Beethoven's Bagatelle in A minor, WoO 59. Ludwig Nohl, who published it in 1867 (forty years after Beethoven's death), said the autograph was inscribed "Für Elise am 27 April [1810] zur Erinnerung von L. v. Bthvn." That autograph is lost. Beethoven returned to the piece in 1822 and reworked the accompaniment; Barry Cooper has transcribed that later version, marked Molto grazioso instead of Nohl's Poco moto.

    Nobody knows who "Elise" was. Max Unger suggested in 1925 that Nohl misread "Für Therese", meaning Therese Malfatti, his pupil, to whom Beethoven is said to have proposed in 1810. Klaus Martin Kopitz proposed the singer Elisabeth Röckel (2010), and Rita Steblin Elise Barensfeld, a 13-year-old prodigy who studied singing with Salieri (2014). None of these is proven.

    ## Playing it
    - It is a rondo, A–B–A–C–A, in 3/8. Feel one beat per bar rather than three, so the famous E–D♯ figure moves as a single gentle gesture.
    - In the refrain the semiquaver line passes between the hands: practise the hand-overs until they make no accent.
    - Lift the pedal at every change of harmony to keep the line clear.
    - The F-major episode (B) is lyrical and light; the stormier episode (C) runs over repeated low A's in the left hand. Keep those soft and even, from a relaxed wrist.
    - Practise the chromatic scale that leads back to the refrain slowly; it should arrive in time, without a ritardando.

    ## Did you know?
    Because the lost autograph has never been seen since Nohl, the musicologist Luca Chiantore has even questioned whether a signed original ever existed.

    ## Sources
    - Wikipedia, "Für Elise": {WIKI}/F%C3%BCr_Elise
""")

ELISE_FR = cleandoc(f"""
    ## Histoire
    La Lettre à Élise est la Bagatelle en la mineur WoO 59 de Beethoven. Ludwig Nohl, qui la publia en 1867 (quarante ans après la mort du compositeur), affirmait que l'autographe portait l'inscription « Für Elise am 27 April [1810] zur Erinnerung von L. v. Bthvn. » Cet autographe est perdu. Beethoven reprit la pièce en 1822 et en retravailla l'accompagnement ; Barry Cooper a transcrit cette version tardive, marquée Molto grazioso au lieu du Poco moto de Nohl.

    Personne ne sait qui était « Élise ». Max Unger suggéra en 1925 que Nohl avait mal lu « Für Therese », c'est-à-dire Therese Malfatti, son élève, à qui Beethoven aurait demandé sa main en 1810. Klaus Martin Kopitz a proposé la chanteuse Elisabeth Röckel (2010), et Rita Steblin Elise Barensfeld, une enfant prodige de 13 ans qui prenait des leçons de chant avec Salieri (2014). Aucune de ces hypothèses n'est prouvée.

    ## Conseils de jeu
    - C'est un rondo A–B–A–C–A à 3/8. Sentez un temps par mesure plutôt que trois : le célèbre motif mi–ré♯ devient un seul geste souple.
    - Dans le refrain, la ligne de doubles croches passe d'une main à l'autre : travaillez ces passages jusqu'à ce qu'ils ne s'entendent plus.
    - Changez de pédale à chaque changement d'harmonie pour garder la ligne claire.
    - L'épisode en fa majeur (B) est chantant et léger ; l'épisode plus agité (C) se déroule sur des la graves répétés à la main gauche. Gardez-les doux et égaux, poignet souple.
    - Travaillez lentement la gamme chromatique qui ramène au refrain : elle doit arriver à temps, sans ralentir.

    ## Le saviez-vous ?
    Comme personne n'a revu l'autographe depuis Nohl, le musicologue Luca Chiantore s'est même demandé si un original signé avait jamais existé.

    ## Sources
    - Wikipédia (en), « Für Elise » : {WIKI}/F%C3%BCr_Elise
""")

PATHETIQUE = cleandoc(f"""
    ## History
    Beethoven wrote this sonata in 1798, aged 27. It came out in Vienna in 1799, published by Hoffmeister as "Grande Sonate pathétique", dedicated to his patron Prince Karl Lichnowsky. Whether the title was Beethoven's idea or the publisher's (with Beethoven's approval) is still debated. The autograph is lost.

    It has three movements: Grave – Allegro di molto e con brio (C minor); Adagio cantabile (A-flat major, a simple rondo); and Rondo: Allegro (C minor). The table of contents lets you jump between them.

    ## Playing it
    - Grave: make the dotted rhythms sharp and the sudden fortepianos real contrasts. The very fast runs are written out: play them as a free flourish, but land on the next beat in time.
    - The slow introduction comes back twice inside the first movement, at the start of the development and in the coda; give it the same weight each time.
    - Allegro: the left-hand tremolo octaves come from a loose forearm rotation, not from the fingers. Practise them as blocked octaves first and stay light.
    - Adagio: the melody and its accompaniment share the right hand. Voice the tune with the outer fingers and keep the inner semiquavers very quiet.
    - Rondo: it is in cut time; think two beats per bar and don't let it run away.

    ## Did you know?
    - Ignaz Moscheles discovered the sonata in 1804, aged ten. Unable to afford the music, he copied it out from a library copy.
    - Billy Joel built the chorus of "This Night" (1983) on the theme of the Adagio; the album credits "L.v. Beethoven" as co-writer.

    ## Sources
    - Wikipedia, "Piano Sonata No. 8 (Beethoven)": {WIKI}/Piano_Sonata_No._8_(Beethoven)
    - IMSLP, Piano Sonata No. 8, Op. 13: https://imslp.org/wiki/Piano_Sonata_No.8,_Op.13_(Beethoven,_Ludwig_van)
    - Wikipedia, "This Night (Billy Joel song)": {WIKI}/This_Night_(Billy_Joel_song)
""")

PATHETIQUE_FR = cleandoc(f"""
    ## Histoire
    Beethoven écrivit cette sonate en 1798, à 27 ans. Elle parut à Vienne en 1799 chez Hoffmeister sous le titre de « Grande Sonate pathétique », dédiée à son protecteur, le prince Karl Lichnowsky. On débat encore pour savoir si le titre vient de Beethoven ou de l'éditeur (avec l'accord du compositeur). L'autographe est perdu.

    Elle compte trois mouvements : Grave – Allegro di molto e con brio (do mineur) ; Adagio cantabile (la bémol majeur, un rondo simple) ; et Rondo : Allegro (do mineur). La table des matières permet de passer de l'un à l'autre.

    ## Conseils de jeu
    - Grave : rythmes pointés incisifs, et de vrais contrastes dans les fortepianos. Les traits très rapides sont écrits : jouez-les comme un geste libre, mais retombez à temps sur le temps suivant.
    - L'introduction lente revient deux fois dans le premier mouvement, au début du développement et dans la coda : donnez-lui le même poids à chaque fois.
    - Allegro : les octaves en trémolo de la main gauche viennent d'une rotation souple de l'avant-bras, pas des doigts. Travaillez-les d'abord en octaves plaquées et restez léger.
    - Adagio : la mélodie et son accompagnement se partagent la main droite. Faites chanter la mélodie avec les doigts extérieurs et gardez les doubles croches intérieures très douces.
    - Rondo : il est à alla breve ; pensez deux temps par mesure et ne vous laissez pas emporter.

    ## Le saviez-vous ?
    - Ignaz Moscheles découvrit la sonate en 1804, à dix ans. Trop pauvre pour acheter la partition, il la recopia à partir d'un exemplaire de bibliothèque.
    - Billy Joel a construit le refrain de « This Night » (1983) sur le thème de l'Adagio ; l'album crédite « L.v. Beethoven » comme coauteur.

    ## Sources
    - Wikipédia (en), « Piano Sonata No. 8 (Beethoven) » : {WIKI}/Piano_Sonata_No._8_(Beethoven)
    - IMSLP, Sonate pour piano n° 8, op. 13 : https://imslp.org/wiki/Piano_Sonata_No.8,_Op.13_(Beethoven,_Ludwig_van)
    - Wikipédia (en), « This Night (Billy Joel song) » : {WIKI}/This_Night_(Billy_Joel_song)
""")

CHOPIN_28_4 = cleandoc(f"""
    ## History
    This is the fourth of Chopin's 24 Preludes, Op. 28, one in each key. He wrote them between 1835 and 1839, mostly in Paris, and finished most of them in Valldemossa, Mallorca, where he spent the winter of 1838–39 with George Sand. They were published in 1839: the French and English editions are dedicated to the piano maker Camille Pleyel, who had paid 2,000 francs for them, and the German edition to Joseph Christoph Kessler. The tempo marking is Largo.

    At Chopin's own request, this prelude and No. 6 in B minor were played at his funeral at the Madeleine in Paris on 30 October 1849, on the organ by Louis Lefébure-Wély, along with Mozart's Requiem.

    ## Playing it
    - The right hand barely moves (B and C, again and again): give the melody a singing weight and a little freedom.
    - The left-hand chords change one note at a time, mostly by half steps. Play them very softly and legato, and listen for which voice moves each time.
    - Change the pedal with every left-hand harmony; half-pedalling keeps it clear.
    - The only outburst is the sudden fortissimo at bar 16, when the opening returns. Build towards it and let it fall away.
    - Give the rests before the final chords their full length. The last dynamic is smorzando, "dying away".

    ## Did you know?
    - The conductor Hans von Bülow nicknamed it "Suffocation".
    - George Sand gave each prelude a title, in a score that is now lost; "Quelles larmes au fond du cloître humide?" ("What tears in the depths of the damp cloister?") is thought to belong to this one.

    ## Sources
    - Wikipedia, "Prelude, Op. 28, No. 4 (Chopin)": {WIKI}/Prelude,_Op._28,_No._4_(Chopin)
    - Wikipedia, "Preludes (Chopin)": {WIKI}/Preludes_(Chopin)
    - Wikipedia, "Alfred Lefébure-Wély": {WIKI}/Alfred_Lef%C3%A9bure-W%C3%A9ly
""")

CHOPIN_28_4_FR = cleandoc(f"""
    ## Histoire
    C'est le quatrième des 24 Préludes op. 28 de Chopin, un dans chaque tonalité. Il les écrivit entre 1835 et 1839, surtout à Paris, et en termina la plupart à Valldemossa, à Majorque, où il passa l'hiver 1838–39 avec George Sand. Ils parurent en 1839 : les éditions française et anglaise sont dédiées au facteur de pianos Camille Pleyel, qui les avait payés 2 000 francs, et l'édition allemande à Joseph Christoph Kessler. L'indication de tempo est Largo.

    À la demande de Chopin lui-même, ce prélude et le n° 6 en si mineur furent joués à ses funérailles, à la Madeleine à Paris, le 30 octobre 1849, à l'orgue par Louis Lefébure-Wély, avec le Requiem de Mozart.

    ## Conseils de jeu
    - La main droite bouge à peine (si et do, encore et encore) : donnez à la mélodie un poids chantant et un peu de liberté.
    - Les accords de la main gauche changent une note à la fois, surtout par demi-tons. Jouez-les très doucement et legato, en écoutant quelle voix bouge à chaque fois.
    - Changez de pédale à chaque harmonie de la main gauche ; une demi-pédale garde la clarté.
    - Le seul éclat est le fortissimo soudain de la mesure 16, au retour du début. Construisez-le, puis laissez-le retomber.
    - Donnez aux silences avant les derniers accords toute leur durée. La dernière nuance est smorzando, « en s'éteignant ».

    ## Le saviez-vous ?
    - Le chef d'orchestre Hans von Bülow le surnommait « Suffocation ».
    - George Sand avait donné un titre à chaque prélude, dans une partition aujourd'hui perdue ; « Quelles larmes au fond du cloître humide ? » correspondrait à celui-ci.

    ## Sources
    - Wikipédia (en), « Prelude, Op. 28, No. 4 (Chopin) » : {WIKI}/Prelude,_Op._28,_No._4_(Chopin)
    - Wikipédia (en), « Preludes (Chopin) » : {WIKI}/Preludes_(Chopin)
    - Wikipédia (en), « Alfred Lefébure-Wély » : {WIKI}/Alfred_Lef%C3%A9bure-W%C3%A9ly
""")

TRAUMEREI = cleandoc(f"""
    ## History
    Träumerei ("Dreaming") is No. 7 of Schumann's Kinderszenen (Scenes from Childhood), Op. 15, written in February and March 1838. Schumann told Clara Wieck, his future wife, that her remark that he sometimes seemed "like a child" had inspired some thirty "droll little things"; he kept thirteen. The titles were added afterwards, and he called them "nothing more than delicate hints for execution and interpretation".

    These are not pieces for children to play. In a letter to Carl Reinecke of 6 October 1848, Schumann called the Kinderszenen "reflections of an older person for older people", unlike his Album for the Young.

    ## Playing it
    - The whole piece grows from one phrase: an upbeat that climbs to a long high note. Give that note time to sing before the line comes down.
    - The texture is in several voices and the melody moves between the hands and into the inner voices. Find where it is in each bar and let the other voices answer it.
    - Use a supple tempo inside each phrase, but come back to the pulse. Honour the fermatas.
    - Change the pedal with the harmony, often twice a bar, so the inner voices stay clear.

    ## Did you know?
    When Vladimir Horowitz returned to Moscow on 20 April 1986, after more than sixty years away, Träumerei was his first encore, and the cameras filming the concert caught listeners in tears.

    ## Sources
    - Wikipedia, "Kinderszenen": {WIKI}/Kinderszenen
    - All Classical Portland, "Scenes from Childhood, Op. 15": https://research.allclassical.org/?p=2024
    - MusicWeb International, review of the "Horowitz in Moscow" DVD: https://www.musicweb-international.com/classrev/2006/may06/Horowitz_in_Moscow%20_SVD64545.htm
""")

TRAUMEREI_FR = cleandoc(f"""
    ## Histoire
    Träumerei (« Rêverie ») est le n° 7 des Kinderszenen (Scènes d'enfants) op. 15 de Schumann, écrites en février et mars 1838. Schumann raconta à Clara Wieck, sa future épouse, que sa remarque — il lui semblait parfois « comme un enfant » — lui avait inspiré une trentaine de « petites choses drôles » ; il en garda treize. Les titres furent ajoutés après coup, et il les qualifiait de « rien de plus que de délicates indications pour l'exécution et l'interprétation ».

    Ce ne sont pas des pièces à faire jouer aux enfants. Dans une lettre à Carl Reinecke du 6 octobre 1848, Schumann décrivait les Kinderszenen comme des « reflets d'un adulte pour des adultes », à la différence de son Album pour la jeunesse.

    ## Conseils de jeu
    - Toute la pièce naît d'une seule phrase : une anacrouse qui monte vers une longue note aiguë. Laissez chanter cette note avant que la ligne redescende.
    - L'écriture est à plusieurs voix et la mélodie passe d'une main à l'autre et dans les voix intérieures. Repérez-la dans chaque mesure et laissez les autres voix lui répondre.
    - Gardez un tempo souple à l'intérieur de chaque phrase, mais revenez à la pulsation. Respectez les points d'orgue.
    - Changez de pédale avec l'harmonie, souvent deux fois par mesure, pour garder les voix intérieures claires.

    ## Le saviez-vous ?
    Quand Vladimir Horowitz revint jouer à Moscou le 20 avril 1986, après plus de soixante ans d'absence, Träumerei fut son premier bis, et les caméras qui filmaient le concert ont saisi des auditeurs en larmes.

    ## Sources
    - Wikipédia (en), « Kinderszenen » : {WIKI}/Kinderszenen
    - All Classical Portland, « Scenes from Childhood, Op. 15 » : https://research.allclassical.org/?p=2024
    - MusicWeb International, critique du DVD « Horowitz in Moscow » : https://www.musicweb-international.com/classrev/2006/may06/Horowitz_in_Moscow%20_SVD64545.htm
""")

GYMNOPEDIE = cleandoc(f"""
    ## History
    Erik Satie, aged 21, finished his three Gymnopédies by 2 April 1888. No. 1 was published that summer in the magazine La Musique des familles, next to a poem by his friend J. P. Contamine de Latour, "Les Antiques", which uses the word "gymnopédie"; nobody knows whether the poem or the music came first. The word comes from the gymnopaedia, a festival of ancient Sparta where young men danced unclothed. Satie and his biographer Alexis Roland-Manuel said he found it in Flaubert's novel Salammbô.

    The marking is "Lent et douloureux" (slow and sorrowful), in 3/4.

    ## Playing it
    - The left hand alternates a low bass note on beat 1 with a chord on beat 2. Practise the leap until you can make it without looking, and keep the chord softer than the bass.
    - The opening harmonies simply rock between two chords (G major seventh and D major seventh). Let that rocking stay perfectly regular.
    - The melody enters in bar 5. Play it legato and plainly: the stillness is the expression, so add very little rubato.
    - Pedal once per bar, catching the bass note and clearing just before the next one.

    ## Did you know?
    - Claude Debussy orchestrated the first and third Gymnopédies in February 1897. When the scores were published, he swapped their numbers, so Satie's No. 1 is Debussy's No. 3.
    - Blood, Sweat & Tears recorded "Variations on a Theme by Erik Satie" (1968), and Janet Jackson sampled No. 1 in "Someone to Call My Lover" (2001).

    ## Sources
    - Wikipedia, "Gymnopédies": {WIKI}/Gymnop%C3%A9dies
""")

GYMNOPEDIE_FR = cleandoc(f"""
    ## Histoire
    Erik Satie, à 21 ans, acheva ses trois Gymnopédies au plus tard le 2 avril 1888. La première parut l'été suivant dans la revue La Musique des familles, à côté d'un poème de son ami J. P. Contamine de Latour, « Les Antiques », où figure le mot « gymnopédie » ; on ne sait pas si le poème ou la musique est venu en premier. Le mot vient des gymnopédies, une fête de l'ancienne Sparte où de jeunes hommes dansaient nus. Satie et son biographe Alexis Roland-Manuel disaient qu'il l'avait trouvé dans Salammbô de Flaubert.

    L'indication est « Lent et douloureux », à 3/4.

    ## Conseils de jeu
    - La main gauche alterne une basse grave sur le premier temps et un accord sur le deuxième. Travaillez le saut jusqu'à pouvoir le faire sans regarder, et gardez l'accord plus doux que la basse.
    - Les harmonies du début se balancent entre deux accords (sol majeur septième et ré majeur septième). Gardez ce balancement parfaitement régulier.
    - La mélodie entre à la mesure 5. Jouez-la legato et simplement : c'est l'immobilité qui exprime, alors très peu de rubato.
    - Une pédale par mesure : prenez la basse et relevez juste avant la suivante.

    ## Le saviez-vous ?
    - Claude Debussy orchestra la première et la troisième Gymnopédie en février 1897. À la publication, il inversa leurs numéros : la n° 1 de Satie est la n° 3 de Debussy.
    - Blood, Sweat & Tears a enregistré « Variations on a Theme by Erik Satie » (1968), et Janet Jackson a échantillonné la n° 1 dans « Someone to Call My Lover » (2001).

    ## Sources
    - Wikipédia (en), « Gymnopédies » : {WIKI}/Gymnop%C3%A9dies
""")
