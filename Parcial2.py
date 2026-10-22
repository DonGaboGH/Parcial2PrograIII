"""Visor del inventario de las sucursales de la empresa."""

from pathlib import Path
import sys

import pandas as pd
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg
from matplotlib.figure import Figure
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor
from PyQt5.QtWidgets import (
    QApplication,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)


RUTA_INVENTARIO = Path(__file__).with_name("inventario_sucursales.csv")
SUCURSALES = (
    "San Salvador",
    "Santa Ana",
    "San Miguel",
    "La Libertad",
    "Sonsonate",
)
COLUMNAS_REQUERIDAS = {
    "Sucursal",
    "Producto",
    "Categoria",
    "Cantidad",
    "Precio_Unitario_USD",
    "Stock_Minimo",
}


def cargar_inventario(ruta: Path = RUTA_INVENTARIO) -> pd.DataFrame:
    """Carga y valida el CSV antes de usarlo en el análisis y la interfaz."""
    inventario = pd.read_csv(ruta, encoding="utf-8-sig")
    faltantes = COLUMNAS_REQUERIDAS.difference(inventario.columns)
    if faltantes:
        raise ValueError(
            "Al inventario le faltan las columnas requeridas: "
            + ", ".join(sorted(faltantes))
        )
    if inventario.empty:
        raise ValueError("El archivo de inventario no contiene registros.")

    sucursales_en_archivo = set(inventario["Sucursal"].dropna())
    sucursales_desconocidas = sucursales_en_archivo.difference(SUCURSALES)
    if sucursales_desconocidas:
        raise ValueError(
            "Se encontraron sucursales no reconocidas: "
            + ", ".join(sorted(sucursales_desconocidas))
        )
    if inventario[list(COLUMNAS_REQUERIDAS)].isna().any().any():
        raise ValueError("El inventario contiene valores vacíos en campos requeridos.")

    columnas_numericas = ["Cantidad", "Precio_Unitario_USD", "Stock_Minimo"]
    for columna in columnas_numericas:
        inventario[columna] = pd.to_numeric(inventario[columna], errors="raise")
    if (inventario[columnas_numericas] < 0).any().any():
        raise ValueError("Las cantidades, precios y mínimos no pueden ser negativos.")

    inventario["Valor_Inventario_USD"] = (
        inventario["Cantidad"] * inventario["Precio_Unitario_USD"]
    )
    return inventario


def inspeccionar_inventario(inventario: pd.DataFrame) -> None:
    """Muestra estructura, tipos, estadísticas y existencias por sucursal."""
    print("\n=== INVENTARIO: PRIMEROS REGISTROS ===")
    print(inventario.head())
    print("\n=== ESTRUCTURA Y VALORES NO NULOS ===")
    inventario.info()
    print("\n=== TIPOS DE DATOS ===")
    print(inventario.dtypes)
    print("\n=== ESTADÍSTICAS DESCRIPTIVAS ===")
    print(inventario.describe(include="all"))
    print("\n=== UNIDADES Y VALOR POR SUCURSAL ===")
    print(
        inventario.groupby("Sucursal")
        .agg(
            Productos=("Producto", "count"),
            Unidades=("Cantidad", "sum"),
            Valor_USD=("Valor_Inventario_USD", "sum"),
        )
        .reindex(SUCURSALES)
        .fillna(0)
    )


class InventarioWindow(QMainWindow):
    """Interfaz para explorar el inventario y comparar sus sucursales."""

    def __init__(self, inventario: pd.DataFrame) -> None:
        super().__init__()
        self.inventario = inventario
        self.setWindowTitle("Inventario de sucursales")
        self.resize(1180, 760)

        central = QWidget()
        layout = QVBoxLayout(central)

        titulo = QLabel("Inventario de productos")
        titulo.setStyleSheet("font-size: 22px; font-weight: bold;")
        layout.addWidget(titulo)

        controles = QHBoxLayout()
        controles.addWidget(QLabel("Filtrar por sucursal:"))
        self.filtro_sucursal = QComboBox()
        self.filtro_sucursal.addItem("Todas las sucursales")
        self.filtro_sucursal.addItems(SUCURSALES)
        self.filtro_sucursal.currentTextChanged.connect(self.actualizar_vista)
        controles.addWidget(self.filtro_sucursal)
        controles.addStretch()
        layout.addLayout(controles)

        resumen = QHBoxLayout()
        self.etiqueta_productos = QLabel()
        self.etiqueta_unidades = QLabel()
        self.etiqueta_valor = QLabel()
        for etiqueta in (
            self.etiqueta_productos,
            self.etiqueta_unidades,
            self.etiqueta_valor,
        ):
            etiqueta.setStyleSheet(
                "font-size: 15px; padding: 10px; "
                "background-color: #eef4f8; border-radius: 5px;"
            )
            resumen.addWidget(etiqueta)
        layout.addLayout(resumen)

        self.tabla = QTableWidget()
        self.tabla.setColumnCount(7)
        self.tabla.setHorizontalHeaderLabels(
            [
                "Sucursal",
                "Producto",
                "Categoría",
                "Cantidad",
                "Precio unitario",
                "Stock mínimo",
                "Valor inventario",
            ]
        )
        self.tabla.setEditTriggers(QTableWidget.NoEditTriggers)
        self.tabla.setAlternatingRowColors(True)
        self.tabla.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.tabla, 1)

        self.figura = Figure(figsize=(10, 4.2), tight_layout=True)
        self.canvas = FigureCanvasQTAgg(self.figura)
        layout.addWidget(self.canvas, 2)

        self.setCentralWidget(central)
        self.actualizar_vista()

    def _datos_filtrados(self) -> pd.DataFrame:
        sucursal = self.filtro_sucursal.currentText()
        if sucursal == "Todas las sucursales":
            return self.inventario
        return self.inventario[self.inventario["Sucursal"] == sucursal]

    def actualizar_vista(self) -> None:
        datos = self._datos_filtrados()
        total_unidades = int(datos["Cantidad"].sum())
        total_valor = datos["Valor_Inventario_USD"].sum()
        self.etiqueta_productos.setText(f"Registros: {len(datos)}")
        self.etiqueta_unidades.setText(f"Unidades disponibles: {total_unidades:,}")
        self.etiqueta_valor.setText(f"Valor estimado: ${total_valor:,.2f}")

        self.tabla.setRowCount(len(datos))
        for fila, (_, registro) in enumerate(datos.iterrows()):
            valores = (
                registro["Sucursal"],
                registro["Producto"],
                registro["Categoria"],
                f'{registro["Cantidad"]:,.0f}',
                f'${registro["Precio_Unitario_USD"]:,.2f}',
                f'{registro["Stock_Minimo"]:,.0f}',
                f'${registro["Valor_Inventario_USD"]:,.2f}',
            )
            for columna, valor in enumerate(valores):
                celda = QTableWidgetItem(str(valor))
                if columna >= 3:
                    celda.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                if (
                    columna == 3
                    and registro["Cantidad"] <= registro["Stock_Minimo"]
                ):
                    celda.setBackground(QColor("#ffe0e0"))
                self.tabla.setItem(fila, columna, celda)
        self.tabla.resizeColumnsToContents()
        self._actualizar_graficos(datos)

    def _actualizar_graficos(self, datos: pd.DataFrame) -> None:
        self.figura.clear()
        grafico_unidades, grafico_valor = self.figura.subplots(1, 2)
        sucursal = self.filtro_sucursal.currentText()

        if sucursal == "Todas las sucursales":
            resumen = (
                datos.groupby("Sucursal")
                .agg(
                    Unidades=("Cantidad", "sum"),
                    Valor=("Valor_Inventario_USD", "sum"),
                )
                .reindex(SUCURSALES)
            )
            etiquetas = list(resumen.index)
            unidades = resumen["Unidades"]
            valores = resumen["Valor"]
            titulo_unidades = "Unidades por sucursal"
            titulo_valor = "Valor del inventario por sucursal"
        else:
            resumen = (
                datos.groupby("Producto")
                .agg(
                    Unidades=("Cantidad", "sum"),
                    Valor=("Valor_Inventario_USD", "sum"),
                )
                .sort_values("Unidades", ascending=False)
            )
            etiquetas = list(resumen.index)
            unidades = resumen["Unidades"]
            valores = resumen["Valor"]
            titulo_unidades = f"Unidades por producto — {sucursal}"
            titulo_valor = f"Valor por producto — {sucursal}"

        grafico_unidades.bar(etiquetas, unidades, color="#2a9d8f")
        grafico_unidades.set_title(titulo_unidades)
        grafico_unidades.set_ylabel("Unidades")
        grafico_unidades.tick_params(axis="x", labelrotation=30)
        grafico_valor.bar(etiquetas, valores, color="#457b9d")
        grafico_valor.set_title(titulo_valor)
        grafico_valor.set_ylabel("USD")
        grafico_valor.tick_params(axis="x", labelrotation=30)
        self.canvas.draw()


def main() -> int:
    aplicacion = QApplication(sys.argv)
    try:
        inventario = cargar_inventario()
    except (OSError, pd.errors.ParserError, ValueError) as error:
        QMessageBox.critical(None, "No se pudo cargar el inventario", str(error))
        return 1

    inspeccionar_inventario(inventario)
    ventana = InventarioWindow(inventario)
    ventana.show()
    return aplicacion.exec_()


if __name__ == "__main__":
    sys.exit(main())