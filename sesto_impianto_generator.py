# Sesto d'Impianto Generator - QGIS Processing Script
# Copyright (C) 2026
# License: GPL-3.0 - https://www.gnu.org/licenses/gpl-3.0.txt
# Genera punti di impianto (rettangolo/quinconce) all'interno di un poligono.
# Esporta KML e/o GeoPackage per navigazione con SW Maps + RTK.
# Versione: 2.0
# Funzionalita: capezzagna, zone esclusione, numerazione serpentina,
#   rotta navigazione, multi-varieta, stima fabbisogno
# Sviluppato da Alessandro Azzurretti


from qgis.core import (
    QgsProcessing,
    QgsProcessingAlgorithm,
    QgsProcessingParameterVectorLayer,
    QgsProcessingParameterNumber,
    QgsProcessingParameterEnum,
    QgsProcessingParameterFeatureSink,
    QgsProcessingParameterBoolean,
    QgsProcessingParameterFileDestination,
    QgsProcessingParameterString,
    QgsFeature,
    QgsFeatureSink,
    QgsField,
    QgsFields,
    QgsGeometry,
    QgsPointXY,
    QgsWkbTypes,
    QgsCoordinateReferenceSystem,
    QgsCoordinateTransform,
    QgsProject,
    QgsVectorFileWriter,
    QgsVectorLayer,
)
from qgis.PyQt.QtCore import QVariant
import math
from datetime import datetime


class SestoImpiantoGenerator(QgsProcessingAlgorithm):

    INPUT = 'INPUT'
    EXCLUSION = 'EXCLUSION'
    REF_LINE = 'REF_LINE'
    BUFFER = 'BUFFER'
    ROW_SPACING = 'ROW_SPACING'
    PLANT_SPACING = 'PLANT_SPACING'
    ANGLE = 'ANGLE'
    PATTERN = 'PATTERN'
    START_CORNER = 'START_CORNER'
    SERPENTINE = 'SERPENTINE'
    VARIETY_NAMES = 'VARIETY_NAMES'
    VARIETY_INTERVAL = 'VARIETY_INTERVAL'
    PREFIX = 'PREFIX'
    OUTPUT = 'OUTPUT'
    EXPORT_KML = 'EXPORT_KML'
    KML_FILE = 'KML_FILE'
    EXPORT_GPKG = 'EXPORT_GPKG'
    GPKG_FILE = 'GPKG_FILE'
    TUTORI_INTERVAL = 'TUTORI_INTERVAL'
    TUTORI_POSITION = 'TUTORI_POSITION'
    N_FILI = 'N_FILI'

    def name(self):
        return 'sesto_impianto_generator'

    def displayName(self):
        return "Sesto d'Impianto Generator"

    def group(self):
        return 'Agricoltura di Precisione'

    def groupId(self):
        return 'agricoltura_precisione'

    def shortHelpString(self):
        return (
            "Genera punti di impianto all'interno di un poligono.\n\n"
            "FUNZIONALITA:\n"
            "- Sesto rettangolare o quinconce\n"
            "- Capezzagna: margine interno dal confine per passaggio mezzi\n"
            "- Zone di esclusione: poligono opzionale per escludere ostacoli\n"
            "- Linea di riferimento: calcola l'angolo file automaticamente\n"
            "- Numerazione serpentina: avanti/indietro per navigazione campo\n"
            "- Rotta di navigazione: percorso fila per fila nel KML\n"
            "- Multi-varieta: piante impollinatore ogni N piante sulla fila\n"
            "- Stima fabbisogno: tutori, pali testata, filo\n"
            "- Export KML e/o GeoPackage per SW Maps\n\n"
            "NOTE:\n"
            "- CRS geografico (WGS84) riproiettato in UTM automaticamente.\n"
            "- Per SW Maps: copia KML in SW_Maps/Maps/kml/ oppure GPKG come layer."
        )

    def createInstance(self):
        return SestoImpiantoGenerator()

    def initAlgorithm(self, config=None):

        # === AREA ===
        self.addParameter(QgsProcessingParameterVectorLayer(
            self.INPUT, 'Poligono area impianto',
            [QgsProcessing.TypeVectorPolygon]
        ))

        param_excl = QgsProcessingParameterVectorLayer(
            self.EXCLUSION,
            'Zone di esclusione (opzionale - fossi, ostacoli)',
            [QgsProcessing.TypeVectorPolygon],
            optional=True
        )
        self.addParameter(param_excl)

        self.addParameter(QgsProcessingParameterNumber(
            self.BUFFER,
            'Capezzagna - margine interno dal confine (m)',
            type=QgsProcessingParameterNumber.Double,
            defaultValue=0.0,
            minValue=0.0,
            maxValue=100.0
        ))

        # === ORIENTAMENTO ===
        param_line = QgsProcessingParameterVectorLayer(
            self.REF_LINE,
            'Linea di riferimento direzione file (opzionale)',
            [QgsProcessing.TypeVectorLine],
            optional=True
        )
        self.addParameter(param_line)

        self.addParameter(QgsProcessingParameterNumber(
            self.ANGLE,
            'Angolo file manuale (gradi, 0=Nord, 90=Est) - ignorato se presente la linea',
            type=QgsProcessingParameterNumber.Double,
            defaultValue=0.0, minValue=0.0, maxValue=360.0
        ))

        # === SESTO ===
        self.addParameter(QgsProcessingParameterNumber(
            self.ROW_SPACING,
            'Distanza tra le file (m)',
            type=QgsProcessingParameterNumber.Double,
            defaultValue=4.0, minValue=0.1, maxValue=1000.0
        ))

        self.addParameter(QgsProcessingParameterNumber(
            self.PLANT_SPACING,
            'Distanza sulla fila (m)',
            type=QgsProcessingParameterNumber.Double,
            defaultValue=2.0, minValue=0.1, maxValue=1000.0
        ))

        self.addParameter(QgsProcessingParameterEnum(
            self.PATTERN, "Tipo sesto d'impianto",
            options=['Rettangolo (file parallele)', 'Quinconce (file sfalsate)'],
            defaultValue=0
        ))

        # === NAVIGAZIONE ===
        self.addParameter(QgsProcessingParameterEnum(
            self.START_CORNER, 'Punto di partenza numerazione',
            options=['Nord-Ovest', 'Nord-Est', 'Sud-Ovest', 'Sud-Est'],
            defaultValue=0
        ))

        self.addParameter(QgsProcessingParameterBoolean(
            self.SERPENTINE,
            'Numerazione serpentina (avanti/indietro alternato)',
            defaultValue=True
        ))

        # === VARIETA ===
        self.addParameter(QgsProcessingParameterString(
            self.VARIETY_NAMES,
            'Nomi varieta separate da virgola (es. Golden,Impollinatore)',
            defaultValue='',
            optional=True
        ))

        self.addParameter(QgsProcessingParameterNumber(
            self.VARIETY_INTERVAL,
            'Intervallo impollinatore (es. 5 = ogni 5 piante 1 impollinatore, 0 = disattivato)',
            type=QgsProcessingParameterNumber.Integer,
            defaultValue=0, minValue=0, maxValue=100
        ))

        # === ETICHETTE ===
        self.addParameter(QgsProcessingParameterString(
            self.PREFIX, 'Prefisso nome punto (es. MELO, VITE)',
            defaultValue='', optional=True
        ))

        # === STIMA FABBISOGNO ===
        self.addParameter(QgsProcessingParameterNumber(
            self.TUTORI_INTERVAL,
            'Tutore ogni N piante (es. 7 = un tutore ogni 7 piante, 0 = nessuno)',
            type=QgsProcessingParameterNumber.Integer,
            defaultValue=0, minValue=0, maxValue=100
        ))

        self.addParameter(QgsProcessingParameterEnum(
            self.TUTORI_POSITION,
            'Posizione tutore',
            options=['Sulla pianta', 'Tra due piante (a meta)'],
            defaultValue=0
        ))

        self.addParameter(QgsProcessingParameterNumber(
            self.N_FILI,
            'Numero fili per fila (0 = nessun filo)',
            type=QgsProcessingParameterNumber.Integer,
            defaultValue=0, minValue=0, maxValue=20
        ))

        # === OUTPUT ===
        self.addParameter(QgsProcessingParameterFeatureSink(
            self.OUTPUT, 'Layer punti impianto'
        ))

        self.addParameter(QgsProcessingParameterBoolean(
            self.EXPORT_KML, 'Esporta KML per SW Maps', defaultValue=True
        ))
        self.addParameter(QgsProcessingParameterFileDestination(
            self.KML_FILE, 'File KML di output',
            fileFilter='KML files (*.kml)', optional=True, defaultValue=''
        ))

        self.addParameter(QgsProcessingParameterBoolean(
            self.EXPORT_GPKG, 'Esporta GeoPackage per SW Maps', defaultValue=False
        ))
        self.addParameter(QgsProcessingParameterFileDestination(
            self.GPKG_FILE, 'File GeoPackage di output',
            fileFilter='GeoPackage files (*.gpkg)', optional=True, defaultValue=''
        ))

    # =====================================================================
    # UTILITA
    # =====================================================================

    def _azimuth_from_line(self, line_layer, feedback):
        for feat in line_layer.getFeatures():
            geom = feat.geometry()
            if geom.isEmpty():
                continue
            if geom.isMultipart():
                polyline = geom.asMultiPolyline()[0]
            else:
                polyline = geom.asPolyline()
            if len(polyline) < 2:
                continue

            p1, p2 = polyline[0], polyline[-1]
            dx = p2.x() - p1.x()
            dy = p2.y() - p1.y()
            angle_deg = math.degrees(math.atan2(dx, dy))
            if angle_deg < 0:
                angle_deg += 360.0

            feedback.pushInfo('Linea di riferimento: azimut = %.1f gradi' % angle_deg)
            return angle_deg

        feedback.reportError('Linea di riferimento non valida, uso angolo manuale.')
        return None

    def _merge_polygon(self, layer, transform=None):
        all_geom = QgsGeometry()
        for feat in layer.getFeatures():
            g = feat.geometry()
            if transform:
                g.transform(transform)
            if all_geom.isEmpty():
                all_geom = g
            else:
                all_geom = all_geom.combine(g)
        return all_geom

    # =====================================================================
    # PROCESSO PRINCIPALE
    # =====================================================================

    def processAlgorithm(self, parameters, context, feedback):

        # -- Lettura parametri --
        layer = self.parameterAsVectorLayer(parameters, self.INPUT, context)
        excl_layer = self.parameterAsVectorLayer(parameters, self.EXCLUSION, context)
        ref_line = self.parameterAsVectorLayer(parameters, self.REF_LINE, context)
        buffer_dist = self.parameterAsDouble(parameters, self.BUFFER, context)
        row_sp = self.parameterAsDouble(parameters, self.ROW_SPACING, context)
        plant_sp = self.parameterAsDouble(parameters, self.PLANT_SPACING, context)
        angle_deg_manual = self.parameterAsDouble(parameters, self.ANGLE, context)
        pattern = self.parameterAsEnum(parameters, self.PATTERN, context)
        start_corner = self.parameterAsEnum(parameters, self.START_CORNER, context)
        serpentine = self.parameterAsBool(parameters, self.SERPENTINE, context)
        variety_str = self.parameterAsString(parameters, self.VARIETY_NAMES, context).strip()
        variety_interval = self.parameterAsInt(parameters, self.VARIETY_INTERVAL, context)
        prefix = self.parameterAsString(parameters, self.PREFIX, context).strip()
        tutori_interval = self.parameterAsInt(parameters, self.TUTORI_INTERVAL, context)
        tutori_pos = self.parameterAsEnum(parameters, self.TUTORI_POSITION, context)
        n_fili = self.parameterAsInt(parameters, self.N_FILI, context)
        export_kml = self.parameterAsBool(parameters, self.EXPORT_KML, context)
        kml_file = self.parameterAsString(parameters, self.KML_FILE, context)
        export_gpkg = self.parameterAsBool(parameters, self.EXPORT_GPKG, context)
        gpkg_file = self.parameterAsString(parameters, self.GPKG_FILE, context)

        # Varieta
        varieties = []
        if variety_str:
            varieties = [v.strip() for v in variety_str.split(',') if v.strip()]

        # Angolo
        if ref_line is not None:
            angle_from_line = self._azimuth_from_line(ref_line, feedback)
            angle_deg = angle_from_line if angle_from_line is not None else angle_deg_manual
        else:
            angle_deg = angle_deg_manual
            feedback.pushInfo('Angolo file: %.1f gradi' % angle_deg)

        source_crs = layer.crs()

        # -- CRS --
        need_transform = False
        to_projected = None
        to_geographic = None
        if source_crs.isGeographic():
            extent = layer.extent()
            clon = extent.center().x()
            clat = extent.center().y()
            utm_zone = int((clon + 180) / 6) + 1
            hemisphere = '6' if clat >= 0 else '7'
            epsg_code = int('32%s%02d' % (hemisphere, utm_zone))
            work_crs = QgsCoordinateReferenceSystem('EPSG:%d' % epsg_code)
            to_projected = QgsCoordinateTransform(source_crs, work_crs, QgsProject.instance())
            to_geographic = QgsCoordinateTransform(work_crs, source_crs, QgsProject.instance())
            need_transform = True
            feedback.pushInfo('CRS -> EPSG:%d' % epsg_code)
        else:
            work_crs = source_crs

        # -- Geometria area --
        all_geom = self._merge_polygon(layer, to_projected if need_transform else None)
        if all_geom.isEmpty():
            feedback.reportError('Nessuna geometria valida!')
            return {self.OUTPUT: None}

        area_totale_ha = all_geom.area() / 10000

        # Capezzagna (buffer negativo)
        if buffer_dist > 0:
            all_geom = all_geom.buffer(-buffer_dist, 8)
            if all_geom.isEmpty():
                feedback.reportError('Capezzagna troppo grande, area residua nulla!')
                return {self.OUTPUT: None}
            feedback.pushInfo('Capezzagna: %.1f m (area netta: %.2f ha)' % (
                buffer_dist, all_geom.area() / 10000))

        # Zone di esclusione
        if excl_layer is not None:
            excl_geom = self._merge_polygon(excl_layer, to_projected if need_transform else None)
            if not excl_geom.isEmpty():
                all_geom = all_geom.difference(excl_geom)
                if all_geom.isEmpty():
                    feedback.reportError('Esclusione ha rimosso tutta l\'area!')
                    return {self.OUTPUT: None}
                feedback.pushInfo('Zone escluse applicate (area netta: %.2f ha)' % (
                    all_geom.area() / 10000))

        area_netta_ha = all_geom.area() / 10000

        tipo_str = 'Quinconce' if pattern == 1 else 'Rettangolo'
        feedback.pushInfo('Sesto: %.1fm x %.1fm, angolo=%.1f, tipo=%s' % (
            row_sp, plant_sp, angle_deg, tipo_str))

        # -- Campi output --
        fields = QgsFields()
        fields.append(QgsField('id', QVariant.Int))
        fields.append(QgsField('fila', QVariant.Int))
        fields.append(QgsField('pianta', QVariant.Int))
        fields.append(QgsField('nome', QVariant.String))
        fields.append(QgsField('varieta', QVariant.String))
        fields.append(QgsField('coord_x', QVariant.Double))
        fields.append(QgsField('coord_y', QVariant.Double))
        fields.append(QgsField('lon', QVariant.Double))
        fields.append(QgsField('lat', QVariant.Double))

        (sink, dest_id) = self.parameterAsSink(
            parameters, self.OUTPUT, context,
            fields, QgsWkbTypes.Point, source_crs
        )

        # -- Generazione griglia --
        bbox = all_geom.boundingBox()
        cx, cy = bbox.center().x(), bbox.center().y()
        diag = math.sqrt(bbox.width() ** 2 + bbox.height() ** 2)
        half_ext = diag / 2 + max(row_sp, plant_sp) * 2

        angle_rad = math.radians(angle_deg)
        cos_a = math.cos(angle_rad)
        sin_a = math.sin(angle_rad)

        n_rows = int(2 * half_ext / row_sp) + 2
        n_plants = int(2 * half_ext / plant_sp) + 2

        raw_points = []
        for i in range(n_rows):
            if feedback.isCanceled():
                break
            dy = -half_ext + i * row_sp
            offset_x = 0.0
            if pattern == 1 and i % 2 == 1:
                offset_x = plant_sp / 2.0
            for j in range(n_plants):
                dx = -half_ext + j * plant_sp + offset_x
                rx = cx + dx * sin_a + dy * cos_a
                ry = cy + dx * cos_a - dy * sin_a
                pt = QgsPointXY(rx, ry)
                if all_geom.contains(QgsGeometry.fromPointXY(pt)):
                    raw_points.append((i, j, pt))
            feedback.setProgress(int(40 * (i + 1) / n_rows))

        if not raw_points:
            feedback.reportError('Nessun punto generato!')
            return {self.OUTPUT: dest_id}

        # -- Ordinamento e raggruppamento in file --
        reverse_row = start_corner in [0, 1]
        reverse_col = start_corner in [1, 3]

        def project_coords(pt):
            ddx = pt.x() - cx
            ddy = pt.y() - cy
            along = ddx * sin_a + ddy * cos_a
            perp = ddx * cos_a - ddy * sin_a
            return along, perp

        projected = []
        for (i, j, pt) in raw_points:
            along, perp = project_coords(pt)
            projected.append((perp, along, pt))

        projected.sort(key=lambda x: (-x[0] if reverse_row else x[0],
                                       -x[1] if reverse_col else x[1]))

        tolerance = min(row_sp, plant_sp) * 0.3
        rows_grouped = []
        current_row = [projected[0]]
        current_perp = projected[0][0]

        for item in projected[1:]:
            if abs(item[0] - current_perp) < tolerance:
                current_row.append(item)
            else:
                rows_grouped.append(current_row)
                current_row = [item]
                current_perp = item[0]
        rows_grouped.append(current_row)

        # -- Assegna varieta alle file --
        def get_variety(pianta_num):
            if not varieties or variety_interval <= 0:
                return varieties[0] if varieties else ''
            if len(varieties) == 1:
                return varieties[0]
            # Pianta impollinatore ogni N piante
            if (pianta_num % variety_interval) == 0 and len(varieties) > 1:
                return varieties[1]
            return varieties[0]

        # -- Scrittura punti --
        export_points = []  # (lat, lon, name, fila, pianta, varieta)
        pali_data = []      # (lat, lon, fila, posizione='inizio'/'fine')
        tutori_data = []    # (lat, lon, fila, pianta, n_tutore)
        fili_data = []      # (lat_i, lon_i, lat_f, lon_f, fila, varieta, lungh_m, n_piante)
        row_lengths = []    # lunghezza di ogni fila per stima fabbisogno
        point_id = 0

        # Funzione helper per convertire punto work_crs -> lat/lon
        def to_latlon(pt_proj):
            if need_transform:
                geom_tmp = QgsGeometry.fromPointXY(pt_proj)
                geom_tmp.transform(to_geographic)
                pt_tmp = geom_tmp.asPoint()
                return pt_tmp.y(), pt_tmp.x()
            elif source_crs != QgsCoordinateReferenceSystem('EPSG:4326'):
                to_wgs = QgsCoordinateTransform(
                    source_crs,
                    QgsCoordinateReferenceSystem('EPSG:4326'),
                    QgsProject.instance()
                )
                geom_tmp = QgsGeometry.fromPointXY(pt_proj)
                geom_tmp.transform(to_wgs)
                pt_tmp = geom_tmp.asPoint()
                return pt_tmp.y(), pt_tmp.x()
            else:
                return pt_proj.y(), pt_proj.x()

        for row_idx, row_pts in enumerate(rows_grouped):
            if feedback.isCanceled():
                break

            fila_num = row_idx + 1

            # Serpentina: file dispari in un verso, pari nell'altro
            if serpentine and row_idx % 2 == 1:
                row_pts.sort(key=lambda x: x[1] if reverse_col else -x[1])
            else:
                row_pts.sort(key=lambda x: -x[1] if reverse_col else x[1])

            varieta_fila = varieties[0] if varieties else ''

            # Calcola lunghezza fila e pali di testata
            if len(row_pts) >= 2:
                p_first = row_pts[0][2]
                p_last = row_pts[-1][2]
                row_len = math.sqrt((p_last.x() - p_first.x())**2 +
                                     (p_last.y() - p_first.y())**2)
                row_lengths.append(row_len)

                # Pali di testata: offset 1m oltre primo e ultimo punto
                if row_len > 0:
                    ux = (p_last.x() - p_first.x()) / row_len
                    uy = (p_last.y() - p_first.y()) / row_len
                    palo_offset = 1.0  # metri

                    pt_palo_inizio = QgsPointXY(
                        p_first.x() - ux * palo_offset,
                        p_first.y() - uy * palo_offset)
                    pt_palo_fine = QgsPointXY(
                        p_last.x() + ux * palo_offset,
                        p_last.y() + uy * palo_offset)

                    lat_i, lon_i = to_latlon(pt_palo_inizio)
                    lat_f, lon_f = to_latlon(pt_palo_fine)
                    pali_data.append((lat_i, lon_i, fila_num, 'inizio'))
                    pali_data.append((lat_f, lon_f, fila_num, 'fine'))

                    # Linea fila (palo-palo) per layer fili
                    lungh_filo = row_len + 2 * palo_offset
                    fili_data.append((
                        lat_i, lon_i, lat_f, lon_f,
                        fila_num, varieta_fila, lungh_filo, len(row_pts)
                    ))

            for plant_idx, (perp, along, pt_proj) in enumerate(row_pts):
                pianta_num = plant_idx + 1
                point_id += 1

                # Varieta: pianta principale o impollinatore
                varieta = get_variety(pianta_num)

                if prefix:
                    wp_name = '%s_F%02dP%03d' % (prefix, fila_num, pianta_num)
                else:
                    wp_name = 'F%02dP%03d' % (fila_num, pianta_num)

                # Coordinate output
                lat, lon = to_latlon(pt_proj)
                coord_x, coord_y = pt_proj.x(), pt_proj.y()

                if need_transform:
                    geom_orig = QgsGeometry.fromPointXY(pt_proj)
                    geom_orig.transform(to_geographic)
                    pt_out = geom_orig.asPoint()
                else:
                    pt_out = pt_proj

                feat = QgsFeature()
                feat.setGeometry(QgsGeometry.fromPointXY(pt_out))
                feat.setAttributes([
                    point_id, fila_num, pianta_num,
                    wp_name, varieta, coord_x, coord_y, lon, lat
                ])
                sink.addFeature(feat, QgsFeatureSink.FastInsert)

                export_points.append((lat, lon, wp_name, fila_num, pianta_num, varieta))

            # Tutori per questa fila: distribuzione uniforme dal centro
            n_plants_row = len(row_pts)
            if tutori_interval > 0 and n_plants_row >= tutori_interval:
                # Calcola quanti tutori servono e distribuiscili uniformemente
                n_tutori = max(1, round(n_plants_row / float(tutori_interval)))
                n_segmenti = n_tutori + 1
                spaziatura = n_plants_row / float(n_segmenti)

                for t in range(1, n_tutori + 1):
                    # Posizione frazionaria (1-based)
                    pos_float = t * spaziatura

                    if tutori_pos == 0:
                        # Sulla pianta: arrotonda alla pianta piu vicina
                        plant_idx = int(round(pos_float)) - 1
                        plant_idx = max(0, min(plant_idx, n_plants_row - 1))
                        tp = row_pts[plant_idx][2]
                        t_lat, t_lon = to_latlon(tp)
                        tutori_data.append((
                            t_lat, t_lon, fila_num,
                            plant_idx + 1, 'sulla_pianta'))
                    else:
                        # Tra due piante: interpola tra le due piante adiacenti
                        idx_a = int(math.floor(pos_float)) - 1
                        idx_b = idx_a + 1
                        idx_a = max(0, min(idx_a, n_plants_row - 1))
                        idx_b = max(0, min(idx_b, n_plants_row - 1))
                        if idx_a != idx_b:
                            p_a = row_pts[idx_a][2]
                            p_b = row_pts[idx_b][2]
                            frac = pos_float - math.floor(pos_float)
                            mid_pt = QgsPointXY(
                                p_a.x() + (p_b.x() - p_a.x()) * frac,
                                p_a.y() + (p_b.y() - p_a.y()) * frac)
                        else:
                            mid_pt = row_pts[idx_a][2]
                        t_lat, t_lon = to_latlon(mid_pt)
                        tutori_data.append((
                            t_lat, t_lon, fila_num,
                            idx_a + 1, 'tra_piante'))

            feedback.setProgress(40 + int(40 * (row_idx + 1) / len(rows_grouped)))

        # =====================================================================
        # STIMA FABBISOGNO
        # =====================================================================
        n_file = len(rows_grouped)
        total_row_length = sum(row_lengths)

        report = []
        report.append('========================================')
        report.append('  STIMA FABBISOGNO IMPIANTO')
        if prefix:
            report.append('  Prefisso: %s' % prefix)
        report.append('  Data: %s' % datetime.now().strftime('%Y-%m-%d %H:%M'))
        report.append('========================================')
        report.append('')

        report.append('--- DATI IMPIANTO ---')
        report.append('Sesto: %.1f m x %.1f m (%s)' % (
            row_sp, plant_sp, 'Quinconce' if pattern == 1 else 'Rettangolo'))
        report.append('Angolo file: %.1f gradi' % angle_deg)
        if buffer_dist > 0:
            report.append('Capezzagna: %.1f m' % buffer_dist)
        report.append('')

        report.append('--- SUPERFICI ---')
        report.append('Superficie totale: %.2f ha' % area_totale_ha)
        report.append('Superficie netta (impianto): %.2f ha' % area_netta_ha)
        report.append('')

        report.append('--- PIANTE ---')
        report.append('Piante totali: %d' % point_id)
        report.append('File totali: %d' % n_file)
        if n_file > 0:
            report.append('Media piante/fila: %d' % (point_id // n_file))
        if area_netta_ha > 0:
            report.append('Densita: %d piante/ha' % int(point_id / area_netta_ha))
        report.append('Piante da acquistare (+5%% scorta): %d' % int(point_id * 1.05))

        # Varieta
        if varieties and variety_interval > 0 and len(varieties) > 1:
            report.append('')
            report.append('--- VARIETA ---')
            report.append('Intervallo impollinatore: ogni %d piante' % variety_interval)
            var_counts = {}
            for _, _, _, _, _, var in export_points:
                var_counts[var] = var_counts.get(var, 0) + 1
            for var_name, count in var_counts.items():
                report.append('  %s: %d piante (+5%% = %d)' % (
                    var_name, count, int(count * 1.05)))

        # Materiale
        report.append('')
        report.append('--- MATERIALE ---')

        if tutori_interval > 0:
            pos_str = 'sulla pianta' if tutori_pos == 0 else 'tra due piante'
            report.append('Tutori: %d (ogni %d piante, %s)' % (
                len(tutori_data), tutori_interval, pos_str))

        pali_testata = n_file * 2
        report.append('Pali di testata: %d (%d file x 2)' % (pali_testata, n_file))

        if n_fili > 0 and fili_data:
            filo_per_fila = [(d[4], d[6]) for d in fili_data]
            filo_totale_m = sum(l for _, l in filo_per_fila) * n_fili
            report.append('Fili per fila: %d' % n_fili)
            report.append('Filo totale: %.0f m = %.1f km' % (
                filo_totale_m, filo_totale_m / 1000))
            report.append('')
            report.append('--- DETTAGLIO FILO PER FILA ---')
            report.append('%-8s  %-10s  %-8s  %s' % ('Fila', 'Lungh.(m)', 'N.fili', 'Totale(m)'))
            for fila_num, lungh in filo_per_fila:
                report.append('%-8s  %-10.1f  %-8d  %.1f' % (
                    'Fila %02d' % fila_num, lungh, n_fili, lungh * n_fili))

        if serpentine:
            report.append('')
            report.append('Navigazione: serpentina attiva')

        report.append('')
        report.append('========================================')

        # Stampa nel log di Processing
        for line in report:
            feedback.pushInfo(line)

        # Salva file report nella stessa cartella dell'output
        import os
        out_file = ''
        if gpkg_file:
            out_file = gpkg_file
        elif kml_file:
            out_file = kml_file

        if out_file:
            report_path = os.path.splitext(out_file)[0] + '.txt'
            try:
                with open(report_path, 'w', encoding='utf-8') as f:
                    f.write('\n'.join(report))
                feedback.pushInfo('')
                feedback.pushInfo('Report salvato: %s' % report_path)
            except Exception as e:
                feedback.reportError('Errore salvataggio report: %s' % str(e))

        # =====================================================================
        # ESPORTAZIONI
        # =====================================================================
        feedback.setProgress(80)

        if export_kml and kml_file:
            self._write_kml(export_points, rows_grouped, kml_file, prefix,
                            serpentine, reverse_col, varieties, variety_interval,
                            need_transform, to_geographic, cx, cy, sin_a, cos_a,
                            feedback)

        if export_gpkg and gpkg_file:
            self._write_gpkg(export_points, pali_data, tutori_data, fili_data,
                             n_fili, gpkg_file, prefix, source_crs, feedback)

        feedback.setProgress(100)
        return {self.OUTPUT: dest_id}

    # =====================================================================
    # EXPORT KML
    # =====================================================================

    def _write_kml(self, points, rows_grouped, filepath, prefix,
                   serpentine, reverse_col, varieties, variety_interval,
                   need_transform, to_geographic, cx, cy, sin_a, cos_a,
                   feedback):

        # Colori per varieta (AABBGGRR in KML)
        var_colors = [
            'ff00aa00',  # verde
            'ff0055ff',  # arancione
            'ff0000ff',  # rosso
            'ffff5500',  # azzurro
            'ff00ffff',  # giallo
        ]

        # Raggruppa per fila
        file_dict = {}
        for lat, lon, wp_name, fila, pianta, var in points:
            if fila not in file_dict:
                file_dict[fila] = []
            file_dict[fila].append((lat, lon, wp_name, pianta, var))

        lines = []
        lines.append('<?xml version="1.0" encoding="UTF-8"?>')
        lines.append('<kml xmlns="http://www.opengis.net/kml/2.2">')
        lines.append('<Document>')

        doc_name = 'Impianto %s' % prefix if prefix else 'Punti Impianto'
        lines.append('<name>%s</name>' % doc_name)
        lines.append('<description>%d punti, %d file - %s</description>' % (
            len(points), len(file_dict),
            datetime.now().strftime('%Y-%m-%d %H:%M')))

        # Stili per varieta
        unique_vars = list(dict.fromkeys([p[5] for p in points]))
        for i, var in enumerate(unique_vars):
            color = var_colors[i % len(var_colors)]
            style_id = 'var_%d' % i
            lines.append('<Style id="%s">' % style_id)
            lines.append('<IconStyle>')
            lines.append('<color>%s</color>' % color)
            lines.append('<scale>0.7</scale>')
            lines.append('<Icon><href>http://maps.google.com/mapfiles/kml/paddle/grn-circle.png</href></Icon>')
            lines.append('</IconStyle>')
            lines.append('<LabelStyle><scale>0.6</scale></LabelStyle>')
            lines.append('</Style>')

        # Mappa varieta -> stile
        var_style_map = {}
        for i, var in enumerate(unique_vars):
            var_style_map[var] = 'var_%d' % i

        # Stile rotta
        lines.append('<Style id="rotta">')
        lines.append('<LineStyle>')
        lines.append('<color>ff00aaff</color>')
        lines.append('<width>2</width>')
        lines.append('</LineStyle>')
        lines.append('</Style>')

        # -- Cartella punti per fila --
        lines.append('<Folder>')
        lines.append('<name>Punti impianto</name>')

        for fila_num in sorted(file_dict.keys()):
            fila_points = file_dict[fila_num]
            var_label = fila_points[0][4]
            folder_name = 'Fila %02d - %s (%d)' % (fila_num, var_label, len(fila_points))
            if not var_label:
                folder_name = 'Fila %02d (%d piante)' % (fila_num, len(fila_points))

            lines.append('<Folder>')
            lines.append('<name>%s</name>' % folder_name)

            for lat, lon, wp_name, pianta, var in fila_points:
                style = var_style_map.get(var, 'var_0')
                lines.append('<Placemark>')
                lines.append('<name>%s</name>' % wp_name)
                lines.append('<description>Fila %d, Pianta %d%s</description>' % (
                    fila_num, pianta, ' - %s' % var if var else ''))
                lines.append('<styleUrl>#%s</styleUrl>' % style)
                lines.append('<Point>')
                lines.append('<coordinates>%.8f,%.8f,0</coordinates>' % (lon, lat))
                lines.append('</Point>')
                lines.append('</Placemark>')

            lines.append('</Folder>')

        lines.append('</Folder>')

        # -- Rotta di navigazione --
        lines.append('<Folder>')
        lines.append('<name>Rotta navigazione</name>')
        lines.append('<Placemark>')
        lines.append('<name>Percorso fila per fila</name>')
        lines.append('<styleUrl>#rotta</styleUrl>')
        lines.append('<LineString>')
        lines.append('<tessellate>1</tessellate>')

        # Costruisci coordinate della rotta: ultimo punto fila N -> primo punto fila N+1
        route_coords = []
        for fila_num in sorted(file_dict.keys()):
            fila_pts = file_dict[fila_num]
            for lat, lon, _, _, _ in fila_pts:
                route_coords.append('%.8f,%.8f,0' % (lon, lat))

        lines.append('<coordinates>')
        lines.append(' '.join(route_coords))
        lines.append('</coordinates>')
        lines.append('</LineString>')
        lines.append('</Placemark>')
        lines.append('</Folder>')

        lines.append('</Document>')
        lines.append('</kml>')

        kml_text = '\n'.join(lines)

        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(kml_text)
            feedback.pushInfo('')
            feedback.pushInfo('KML esportato: %s' % filepath)
            feedback.pushInfo('-> SW Maps: copia in SW_Maps/Maps/kml/')
        except Exception as e:
            feedback.reportError('Errore KML: %s' % str(e))

    # =====================================================================
    # EXPORT GEOPACKAGE
    # =====================================================================

    def _write_gpkg(self, points, pali_data, tutori_data, fili_data,
                    n_fili, filepath, prefix, source_crs, feedback):

        tag = prefix.lower() if prefix else 'impianto'

        # ── Layer 1: PIANTE ──
        lyr_piante = QgsVectorLayer('Point?crs=EPSG:4326', 'piante', 'memory')
        pr = lyr_piante.dataProvider()
        pr.addAttributes([
            QgsField('id', QVariant.Int),
            QgsField('fila', QVariant.Int),
            QgsField('pianta', QVariant.Int),
            QgsField('nome', QVariant.String),
            QgsField('varieta', QVariant.String),
            QgsField('lat', QVariant.Double),
            QgsField('lon', QVariant.Double),
        ])
        lyr_piante.updateFields()

        feats = []
        for idx, (lat, lon, wp_name, fila, pianta, var) in enumerate(points):
            f = QgsFeature()
            f.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(lon, lat)))
            f.setAttributes([idx + 1, fila, pianta, wp_name, var, lat, lon])
            feats.append(f)
        pr.addFeatures(feats)
        lyr_piante.updateExtents()

        opts = QgsVectorFileWriter.SaveVectorOptions()
        opts.driverName = 'GPKG'
        opts.fileEncoding = 'UTF-8'
        opts.layerName = 'piante_%s' % tag

        err = QgsVectorFileWriter.writeAsVectorFormatV3(
            lyr_piante, filepath, QgsProject.instance().transformContext(), opts)

        if err[0] != QgsVectorFileWriter.NoError:
            feedback.reportError('Errore GeoPackage (piante): %s' % str(err))
            return

        feedback.pushInfo('')
        feedback.pushInfo('GeoPackage: %s' % filepath)
        feedback.pushInfo('  Layer piante_%s: %d feature' % (tag, len(points)))

        # ── Layer 2: PALI DI TESTATA ──
        if pali_data:
            lyr_pali = QgsVectorLayer('Point?crs=EPSG:4326', 'pali', 'memory')
            pr2 = lyr_pali.dataProvider()
            pr2.addAttributes([
                QgsField('id', QVariant.Int),
                QgsField('fila', QVariant.Int),
                QgsField('posizione', QVariant.String),
                QgsField('lat', QVariant.Double),
                QgsField('lon', QVariant.Double),
            ])
            lyr_pali.updateFields()

            feats2 = []
            for idx, (lat, lon, fila, pos) in enumerate(pali_data):
                f = QgsFeature()
                f.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(lon, lat)))
                f.setAttributes([idx + 1, fila, pos, lat, lon])
                feats2.append(f)
            pr2.addFeatures(feats2)
            lyr_pali.updateExtents()

            opts2 = QgsVectorFileWriter.SaveVectorOptions()
            opts2.driverName = 'GPKG'
            opts2.fileEncoding = 'UTF-8'
            opts2.layerName = 'pali_testata_%s' % tag
            opts2.actionOnExistingFile = QgsVectorFileWriter.CreateOrOverwriteLayer

            err2 = QgsVectorFileWriter.writeAsVectorFormatV3(
                lyr_pali, filepath, QgsProject.instance().transformContext(), opts2)

            if err2[0] == QgsVectorFileWriter.NoError:
                feedback.pushInfo('  Layer pali_testata_%s: %d feature' % (tag, len(pali_data)))
            else:
                feedback.reportError('Errore GeoPackage (pali): %s' % str(err2))

        # ── Layer 3: TUTORI ──
        if tutori_data:
            lyr_tut = QgsVectorLayer('Point?crs=EPSG:4326', 'tutori', 'memory')
            pr3 = lyr_tut.dataProvider()
            pr3.addAttributes([
                QgsField('id', QVariant.Int),
                QgsField('fila', QVariant.Int),
                QgsField('dopo_pianta', QVariant.Int),
                QgsField('posizione', QVariant.String),
                QgsField('lat', QVariant.Double),
                QgsField('lon', QVariant.Double),
            ])
            lyr_tut.updateFields()

            feats3 = []
            for idx, (lat, lon, fila, pianta_pos, pos_tipo) in enumerate(tutori_data):
                f = QgsFeature()
                f.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(lon, lat)))
                f.setAttributes([idx + 1, fila, pianta_pos, pos_tipo, lat, lon])
                feats3.append(f)
            pr3.addFeatures(feats3)
            lyr_tut.updateExtents()

            opts3 = QgsVectorFileWriter.SaveVectorOptions()
            opts3.driverName = 'GPKG'
            opts3.fileEncoding = 'UTF-8'
            opts3.layerName = 'tutori_%s' % tag
            opts3.actionOnExistingFile = QgsVectorFileWriter.CreateOrOverwriteLayer

            err3 = QgsVectorFileWriter.writeAsVectorFormatV3(
                lyr_tut, filepath, QgsProject.instance().transformContext(), opts3)

            if err3[0] == QgsVectorFileWriter.NoError:
                feedback.pushInfo('  Layer tutori_%s: %d feature' % (tag, len(tutori_data)))
            else:
                feedback.reportError('Errore GeoPackage (tutori): %s' % str(err3))

        # ── Layer 4: FILI / LINEE FILA ──
        if fili_data:
            lyr_fili = QgsVectorLayer('LineString?crs=EPSG:4326', 'fili', 'memory')
            pr4 = lyr_fili.dataProvider()
            pr4.addAttributes([
                QgsField('id', QVariant.Int),
                QgsField('fila', QVariant.Int),
                QgsField('varieta', QVariant.String),
                QgsField('n_piante', QVariant.Int),
                QgsField('lunghezza_m', QVariant.Double),
                QgsField('n_fili', QVariant.Int),
                QgsField('filo_fila_m', QVariant.Double),
            ])
            lyr_fili.updateFields()

            feats4 = []
            for idx, (lat_i, lon_i, lat_f, lon_f, fila, var, lungh, n_p) in enumerate(fili_data):
                f = QgsFeature()
                line_geom = QgsGeometry.fromPolylineXY([
                    QgsPointXY(lon_i, lat_i),
                    QgsPointXY(lon_f, lat_f)
                ])
                f.setGeometry(line_geom)
                filo_per_fila = lungh * n_fili if n_fili > 0 else 0
                f.setAttributes([
                    idx + 1, fila, var, n_p,
                    round(lungh, 1), n_fili, round(filo_per_fila, 1)
                ])
                feats4.append(f)
            pr4.addFeatures(feats4)
            lyr_fili.updateExtents()

            opts4 = QgsVectorFileWriter.SaveVectorOptions()
            opts4.driverName = 'GPKG'
            opts4.fileEncoding = 'UTF-8'
            opts4.layerName = 'fili_%s' % tag
            opts4.actionOnExistingFile = QgsVectorFileWriter.CreateOrOverwriteLayer

            err4 = QgsVectorFileWriter.writeAsVectorFormatV3(
                lyr_fili, filepath, QgsProject.instance().transformContext(), opts4)

            if err4[0] == QgsVectorFileWriter.NoError:
                feedback.pushInfo('  Layer fili_%s: %d linee' % (tag, len(fili_data)))
            else:
                feedback.reportError('Errore GeoPackage (fili): %s' % str(err4))

        feedback.pushInfo('-> SW Maps: aggiungi i layer dal GeoPackage')
