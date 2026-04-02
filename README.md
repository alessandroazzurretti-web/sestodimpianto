# 🌱 Sesto d'Impianto Generator

**Script di Processing per QGIS** — Genera automaticamente i punti di impianto all'interno di un'area poligonale, con esportazione pronta per la navigazione in campo tramite **SW Maps + RTK**.

Pensato per agronomi, vivaisti e tecnici agricoli che devono progettare nuovi impianti arborei (frutteti, vigneti, oliveti, noccioleti...) e portare i punti direttamente in campo con un ricevitore GNSS.

---

## Funzionalità

### Generazione sesto d'impianto

Lo script genera una griglia regolare di punti all'interno di un poligono disegnato in QGIS. Sono supportati due tipi di sesto:

- **Rettangolo** — file parallele con piante allineate tra le file
- **Quinconce** — file parallele con piante sfalsate di mezzo passo nelle file alterne, per ottimizzare l'intercettazione della luce

L'orientamento delle file si imposta in due modi: inserendo manualmente l'angolo in gradi (0° = Nord, 90° = Est), oppure disegnando una **linea di riferimento** su QGIS nella direzione desiderata — lo script calcola l'azimut automaticamente.

### Capezzagna

Il parametro "margine interno" applica un buffer negativo al poligono prima di generare i punti. Se ad esempio imposti 5 metri, i punti partiranno a 5 m dal bordo dell'appezzamento, lasciando spazio per la capofila e il passaggio dei mezzi.

### Zone di esclusione

Puoi fornire un secondo layer poligono che rappresenta ostacoli da evitare: fossi, alberi esistenti, capannoni, strade interpoderali. Lo script sottrae queste aree dal poligono principale prima della generazione, quindi nessun punto cadrà mai in una zona esclusa.

### Numerazione serpentina

Quando attivata, le file vengono numerate con direzione alternata: la fila 1 va da sinistra a destra, la fila 2 da destra a sinistra, la fila 3 di nuovo da sinistra, e così via. Questo rispecchia il percorso naturale di chi cammina tra le file e ottimizza la navigazione in campo con il ricevitore RTK.

### Rotta di navigazione

Nel file KML viene generata una linea che collega tutti i punti nell'ordine di percorrenza (fila per fila, rispettando la serpentina). In SW Maps puoi visualizzarla come traccia da seguire in campo.

### Multi-varietà e impollinatori

Specificando i nomi delle varietà separati da virgola (es. `Golden,Impollinatore`) e un intervallo (es. `5`), lo script assegna automaticamente la varietà impollinatore ogni N piante sulla fila. Ogni pianta nel layer risultante ha l'attributo `varieta` compilato.

L'assegnazione è per pianta, non per fila: in una fila con intervallo 5 avrai pianta 1-4 Golden, pianta 5 Impollinatore, pianta 6-9 Golden, pianta 10 Impollinatore, e così via.

Nel KML le varietà sono visualizzate con colori diversi per un immediato riscontro visivo.

### Tutori con distribuzione uniforme

I tutori vengono posizionati ogni N piante con distribuzione uniforme e simmetrica. Lo script calcola il numero di tutori necessari per la fila e li distribuisce in modo che lo scarto alle estremità sia uguale da entrambi i lati.

Ad esempio, con 23 piante e intervallo 10: 2 tutori alle posizioni 8 e 15, creando tre segmenti di 8-7-8 piante.

Si può scegliere se posizionare il tutore:

- **Sulla pianta** — il tutore coincide con la posizione della pianta più vicina
- **Tra due piante** — il tutore è posizionato nel punto interpolato tra le due piante adiacenti

### Pali di testata

Vengono generati automaticamente due punti per ogni fila, posizionati 1 metro oltre la prima e l'ultima pianta lungo la direzione della fila. Rappresentano i pali di testata dell'impalcatura.

### Stima fabbisogno materiale

Al termine della generazione, lo script produce un report completo con:

- Piante totali e per varietà, con il +5% di scorta
- Numero di tutori e posizionamento
- Pali di testata (2 per fila)
- Filo totale in metri e km, con dettaglio per fila (lunghezza palo-palo × numero fili)
- Superficie totale e netta, densità piante/ha

Il report viene salvato come file `.txt` nella stessa cartella del file di output, con lo stesso nome (es. `impianto_melo.gpkg` → `impianto_melo.txt`).

### Esportazione

Lo script esporta in due formati, attivabili indipendentemente:

**KML** — File singolo con:
- Cartella per ogni fila contenente i punti pianta
- Colori diversi per varietà
- Linea rotta di navigazione
- Pronto per SW Maps: copiare in `SW_Maps/Maps/kml/` sul telefono

**GeoPackage** — File multi-layer con:
- `piante_[prefisso]` — punti pianta con tutti gli attributi
- `pali_testata_[prefisso]` — punti pali di testata (inizio/fine fila)
- `tutori_[prefisso]` — punti tutori con distribuzione uniforme
- `fili_[prefisso]` — linee da palo a palo per ogni fila, con lunghezza e stima filo

In SW Maps ogni layer può essere acceso o spento indipendentemente a seconda dell'operazione in corso.

### Gestione CRS

Se il layer è in coordinate geografiche (WGS84 / EPSG:4326), lo script rileva automaticamente la zona UTM corretta dall'estensione del layer e riproietta internamente per tutti i calcoli in metri. I risultati vengono riportati nel CRS originale del progetto.

---

## Installazione

### Requisiti

- QGIS 3.x (testato su QGIS 3.34 LTR)

### Metodo 1 — Copia manuale

Copia il file `sesto_impianto_generator.py` nella cartella degli script di Processing:

| Sistema operativo | Percorso |
|---|---|
| Windows | `%appdata%\QGIS\QGIS3\profiles\default\processing\scripts\` |
| Linux | `~/.local/share/QGIS/QGIS3/profiles/default/processing/scripts/` |
| macOS | `~/Library/Application Support/QGIS/QGIS3/profiles/default/processing/scripts/` |

> **Nota:** su Windows la cartella `AppData` è nascosta. Incolla `%appdata%\QGIS\QGIS3\profiles\default\processing\scripts\` direttamente nella barra degli indirizzi di Esplora File. Se la cartella `scripts` non esiste, creala.

Dopo la copia, riavvia QGIS oppure aggiorna la Sketched di Processing.

### Metodo 2 — Da QGIS

1. Apri **Processing → Sketched** (`Ctrl+Alt+T`)
2. In alto, icona **Script** → **Aggiungi script da file...**
3. Seleziona `sesto_impianto_generator.py`

Lo strumento apparirà in: **Processing Sketched → Agricoltura di Precisione → Sesto d'Impianto Generator**

---

## Utilizzo

### Parametri

| Parametro | Descrizione | Default |
|---|---|---|
| **Poligono area impianto** | Layer poligonale con l'area da impiantare | — |
| **Zone di esclusione** | Layer poligonale opzionale con aree da evitare | — |
| **Capezzagna** | Margine interno dal confine, in metri | 0 |
| **Linea di riferimento** | Layer linea opzionale per l'orientamento delle file | — |
| **Angolo file manuale** | Azimut in gradi (0=Nord, 90=Est). Ignorato se presente la linea | 0 |
| **Distanza tra le file** | Spaziatura tra file parallele, in metri | 4.0 |
| **Distanza sulla fila** | Spaziatura tra piante nella stessa fila, in metri | 2.0 |
| **Tipo sesto** | Rettangolo o Quinconce | Rettangolo |
| **Punto di partenza** | Da dove inizia la numerazione: NO, NE, SO, SE | Nord-Ovest |
| **Numerazione serpentina** | Alterna la direzione fila per fila | Sì |
| **Nomi varietà** | Separate da virgola (es. `Golden,Impollinatore`) | — |
| **Intervallo impollinatore** | Ogni N piante, 0 = disattivato | 0 |
| **Prefisso nome punto** | Es. `MELO`, `VITE` — compare nei nomi waypoint | — |
| **Tutore ogni N piante** | 0 = nessun tutore | 0 |
| **Posizione tutore** | Sulla pianta oppure tra due piante | Sulla pianta |
| **Numero fili per fila** | Per calcolo filo totale, 0 = nessuno | 0 |
| **Esporta KML** | Genera file KML per SW Maps | Sì |
| **Esporta GeoPackage** | Genera file GPKG multi-layer | No |

### Esempio pratico: frutteto di meli

1. Disegna il poligono dell'appezzamento in QGIS
2. Disegna un poligono per il fosso da escludere (opzionale)
3. Disegna una linea nella direzione desiderata delle file
4. Apri lo script dalla Processing Sketched
5. Imposta:
   - Distanza tra le file: **4.0 m**
   - Distanza sulla fila: **1.5 m**
   - Capezzagna: **5 m**
   - Tipo: **Rettangolo**
   - Varietà: **Golden,Fuji Impollinatore**
   - Intervallo impollinatore: **5**
   - Prefisso: **MELO**
   - Tutore ogni: **7** piante, **tra due piante**
   - Fili: **3**
6. Esporta KML + GeoPackage
7. Trasferisci i file sul telefono

### Importare in SW Maps

**KML:**
1. Copia il file `.kml` nella cartella `SW_Maps/Maps/kml/` del telefono
2. In SW Maps: icona Layer → Aggiungi → KML → seleziona il file

**GeoPackage:**
1. Copia il file `.gpkg` sul telefono
2. In SW Maps: icona Layer → Aggiungi → GeoPackage → seleziona il file e i layer desiderati

### Navigazione in campo

- Ordina i waypoint per nome per seguire la sequenza serpentina
- Il formato `F01P001` indica Fila 01, Pianta 001
- La rotta nel KML mostra il percorso ottimale fila per fila
- Con RTK centimetrico, posiziona il picchetto/pianta quando la precisione è sufficiente

---

## Output

### Layer punti (QGIS + GeoPackage)

| Campo | Tipo | Descrizione |
|---|---|---|
| `id` | Int | Numero progressivo |
| `fila` | Int | Numero della fila |
| `pianta` | Int | Numero della pianta nella fila |
| `nome` | String | Nome waypoint (es. `MELO_F01P001`) |
| `varieta` | String | Nome della varietà assegnata |
| `coord_x` | Double | Coordinata X nel CRS del progetto |
| `coord_y` | Double | Coordinata Y nel CRS del progetto |
| `lon` | Double | Longitudine WGS84 |
| `lat` | Double | Latitudine WGS84 |

### Layer pali di testata (GeoPackage)

| Campo | Tipo | Descrizione |
|---|---|---|
| `id` | Int | Numero progressivo |
| `fila` | Int | Numero della fila |
| `posizione` | String | `inizio` o `fine` |
| `lat` / `lon` | Double | Coordinate WGS84 |

### Layer tutori (GeoPackage)

| Campo | Tipo | Descrizione |
|---|---|---|
| `id` | Int | Numero progressivo |
| `fila` | Int | Numero della fila |
| `dopo_pianta` | Int | Posizione di riferimento |
| `posizione` | String | `sulla_pianta` o `tra_piante` |
| `lat` / `lon` | Double | Coordinate WGS84 |

### Layer fili (GeoPackage)

| Campo | Tipo | Descrizione |
|---|---|---|
| `id` | Int | Numero progressivo |
| `fila` | Int | Numero della fila |
| `varieta` | String | Varietà prevalente della fila |
| `n_piante` | Int | Piante nella fila |
| `lunghezza_m` | Double | Lunghezza palo-palo in metri |
| `n_fili` | Int | Numero fili impostato |
| `filo_fila_m` | Double | Filo totale per la fila (lunghezza × n_fili) |

---

## Screenshot

### Interfaccia dello script in QGIS

Il pannello parametri è diviso in sezioni logiche: area, orientamento, sesto, navigazione, varietà, materiale ed export.

![Parametri parte 1](docs/interfaccia_parametri_1.png)

![Parametri parte 2](docs/interfaccia_parametri_2.png)

### Risultato in QGIS

Punti di impianto generati all'interno del poligono (viola), con la linea di riferimento per la direzione delle file (rosso).

![QGIS con punti e direzione](docs/qgis_punti_direzione.png)

### Navigazione in campo con SW Maps

Selezione dei layer dal GeoPackage: piante, pali di testata, tutori e fili, ciascuno attivabile indipendentemente.

![Selezione layer GeoPackage](docs/swmaps_layer_selection.jpg)

Tutti i layer visualizzati insieme: linee fila (giallo), punti pianta (giallo), tutori e pali di testata (rosso).

![SW Maps tutti i layer](docs/swmaps_tutti_layer.jpg)

Vista ravvicinata con layer piante e tutori sovrapposti all'ortofoto.

![SW Maps in campo](docs/swmaps_campo.jpg)

---

## Note tecniche

- **Multi-poligono:** se il layer contiene più feature vengono unite automaticamente prima della generazione
- **Performance:** testato fino a circa 50.000 punti senza problemi
- **Quinconce:** le file pari sono sfalsate di metà passo sulla fila
- **Distribuzione tutori:** algoritmo simmetrico che divide la fila in segmenti uguali, minimizzando lo scarto alle estremità
- **Pali di testata:** posizionati con offset di 1 metro oltre la prima e ultima pianta lungo la direzione della fila

---

## Licenza

Questo progetto è rilasciato con licenza [GPL-3.0](LICENSE). Chiunque può usare, modificare e redistribuire lo script, a condizione che le modifiche vengano rilasciate con la stessa licenza open source.

---

## Contribuire

Segnalazioni di bug, richieste di funzionalità e pull request sono benvenute. Apri una [issue](../../issues) per discutere modifiche importanti prima di procedere.
