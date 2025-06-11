#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# version 2.1 by Serge12
"""
BOT DE SCALPING PARA ETH/USDT - VERSIÓN ANDROID (TERMUX)
Estrategia: Cruce de EMA + RSI en timeframe de 5 minutos
Características:
- Stop Loss y Take Profit automáticos
- Gestión de riesgo configurable
- Logging detallado
- Optimizado para Termux
"""

# ==================== 📦 IMPORTACIONES ====================
import ccxt                # Conexión con Binance
import pandas as pd        # Análisis de datos
import time                # Control de intervalos
from datetime import datetime  # Manejo de tiempos
import logging             # Registro de operaciones

# ==================== ⚙️ CONFIGURACIÓN ====================
# 🔄 REEMPLAZA ESTOS VALORES CON TUS CLAVES DE BINANCE
API_KEY = "api aqui" # Tu API Key de Binance
API_SECRET = "secret api aqui"   # Tu Secret Key de Binance
TEST_MODE = False                    # True=Pruebas, False=Real

# ==================== 🤖 CLASE PRINCIPAL ====================
class EthereumScalper:
    def __init__(self, api_key: str, secret_key: str):
        """
        Inicializa el bot con las credenciales de Binance
        📌 Parámetros ajustables en esta sección:
        """
        # Configuración del exchange
        self.exchange = ccxt.binance({
            'apiKey': api_key,
            'secret': secret_key,
            'enableRateLimit': True,  # Evita bloqueos por rate limit
            'options': {
                'defaultType': 'future',  # Trading de futuros
                'adjustForTimeDifference': True  # Ajuste de hora
            }
        })
        
        # 🔄 PARÁMETROS DE TRADING (AJUSTABLES)
        self.symbol = 'ETH/USDT'     # Par a operar
        self.timeframe = '5m'        # Intervalo temporal (1m, 5m, 15m, etc.)
        self.amount = 0.05           # Cantidad de ETH por operación
        self.leverage = 10           # Apalancamiento (1-125x)
        self.stop_loss = 0.008       # 0.8% de stop loss
        self.take_profit = 0.015     # 1.5% de take profit
        
        # 🔄 PARÁMETROS DE ESTRATEGIA (AJUSTABLES)
        self.ema_fast = 9            # EMA rápida (periodos)
        self.ema_slow = 21           # EMA lenta (periodos)
        self.rsi_period = 14         # Periodos para RSI
        self.rsi_overbought = 70      # Nivel de sobrecompra
        self.rsi_oversold = 30        # Nivel de sobreventa
        
        # Variables de estado (no modificar)
        self.current_position = None  # Posición actual
        self.setup()

    def setup(self):
        """Configura el mercado y el apalancamiento"""
        try:
            self.exchange.load_markets()
            
            # Configuración de precisión decimal
            market = self.exchange.market(self.symbol)
            self.price_precision = market['precision']['price']
            self.amount_precision = market['precision']['amount']
            
            # Establece apalancamiento y modo de margen
            self.exchange.set_leverage(self.leverage, self.symbol)
            self.exchange.set_margin_mode('cross', self.symbol)
            
            logging.info(f"✅ Configuración completada para {self.symbol}")
            logging.info(f"📊 Precisiones - Precio: {self.price_precision} | Cantidad: {self.amount_precision}")
            logging.info(f"⚖️ Apalancamiento: {self.leverage}x | SL: {self.stop_loss*100}% | TP: {self.take_profit*100}%")
        except Exception as e:
            logging.error(f"❌ Error en configuración: {e}")
            raise

    # ==================== 📊 ANÁLISIS DE DATOS ====================
    def get_market_data(self):
        """Obtiene datos OHLCV de Binance"""
        try:
            ohlcv = self.exchange.fetch_ohlcv(
                self.symbol, 
                self.timeframe, 
                limit=100  # Cantidad de velas históricas
            )
            df = pd.DataFrame(
                ohlcv, 
                columns=['timestamp', 'open', 'high', 'low', 'close', 'volume']
            )
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            df.set_index('timestamp', inplace=True)
            return df
        except Exception as e:
            logging.error(f"❌ Error obteniendo datos: {e}")
            raise

    def calculate_indicators(self, df):
        """Calcula indicadores técnicos"""
        try:
            # EMA (Medias Móviles Exponenciales)
            df['ema_fast'] = df['close'].ewm(
                span=self.ema_fast, 
                adjust=False
            ).mean().round(self.price_precision)
            
            df['ema_slow'] = df['close'].ewm(
                span=self.ema_slow, 
                adjust=False
            ).mean().round(self.price_precision)
            
            # RSI (Índice de Fuerza Relativa)
            delta = df['close'].diff()
            gain = (delta.where(delta > 0, 0)).fillna(0)
            loss = (-delta.where(delta < 0, 0)).fillna(0)
            
            avg_gain = gain.ewm(
                alpha=1/self.rsi_period, 
                min_periods=self.rsi_period
            ).mean()
            
            avg_loss = loss.ewm(
                alpha=1/self.rsi_period, 
                min_periods=self.rsi_period
            ).mean()
            
            rs = avg_gain / avg_loss
            df['rsi'] = (100 - (100 / (1 + rs))).round(2)
            
            return df
        except Exception as e:
            logging.error(f"❌ Error calculando indicadores: {e}")
            raise

    # ==================== 📈 ESTRATEGIA ====================
    def check_entry_signal(self, df):
        """Verifica señales de entrada al mercado"""
        last = df.iloc[-1]  # Última vela
        prev = df.iloc[-2]  # Vela anterior
        
        # Señal de COMPRA (EMA rápida cruza arriba de la lenta + RSI no sobrecomprado)
        buy_condition = (
            (last['ema_fast'] > last['ema_slow']) and 
            (prev['ema_fast'] <= prev['ema_slow']) and 
            (last['rsi'] < self.rsi_overbought) and
            (last['volume'] > df['volume'].rolling(5).mean().iloc[-1])  # Filtro de volumen
        )
        
        # Señal de VENTA (EMA rápida cruza abajo de la lenta + RSI no sobrevendido)
        sell_condition = (
            (last['ema_fast'] < last['ema_slow']) and 
            (prev['ema_fast'] >= prev['ema_slow']) and 
            (last['rsi'] > self.rsi_oversold) and
            (last['volume'] > df['volume'].rolling(5).mean().iloc[-1])  # Filtro de volumen
        )
        
        return 'buy' if buy_condition else 'sell' if sell_condition else None

    # ==================== 💰 EJECUCIÓN ====================
    def execute_trade(self, signal):
        """Ejecuta órdenes en el mercado"""
        try:
            ticker = self.exchange.fetch_ticker(self.symbol)
            price = round(float(ticker['last']), self.price_precision)
            amount = round(self.amount * self.leverage, self.amount_precision)
            
            logging.info(f"⚡ Señal {signal.upper()} | Precio: {price} | Cantidad: {amount} ETH")
            
            # Orden de mercado
            order = self.exchange.create_order(
                symbol=self.symbol,
                type='MARKET',
                side=signal.upper(),
                amount=amount,
                params={'closePosition': False}
            )
            
            # Coloca protecciones
            self.place_sl_tp(signal, float(order['price']))
            self.current_position = signal
            return order
        except Exception as e:
            logging.error(f"❌ Error ejecutando orden: {e}")
            return None

    def place_sl_tp(self, side, entry_price):
        """Coloca Stop Loss y Take Profit"""
        try:
            amount = round(self.amount * self.leverage, self.amount_precision)
            
            # Cálculo de precios con precisión
            sl_price = round(
                entry_price * (1 - self.stop_loss) if side == 'buy' 
                else entry_price * (1 + self.stop_loss),
                self.price_precision
            )
            
            tp_price = round(
                entry_price * (1 + self.take_profit) if side == 'buy' 
                else entry_price * (1 - self.take_profit),
                self.price_precision
            )
            
            # Orden STOP LOSS
            self.exchange.create_order(
                symbol=self.symbol,
                type='STOP_MARKET',
                side='SELL' if side == 'buy' else 'BUY',
                amount=amount,
                stopPrice=sl_price,
                params={'closePosition': True}
            )
            
            # Orden TAKE PROFIT
            self.exchange.create_order(
                symbol=self.symbol,
                type='TAKE_PROFIT_MARKET',
                side='SELL' if side == 'buy' else 'BUY',
                amount=amount,
                stopPrice=tp_price,
                params={'closePosition': True}
            )
            
            logging.info(f"🛡️ Protecciones colocadas - SL: {sl_price:.2f} | TP: {tp_price:.2f}")
        except Exception as e:
            logging.error(f"⚠️ Error colocando SL/TP: {e}")

    # ==================== 🔄 CICLO PRINCIPAL ====================
    def run(self):
        """Ejecuta el ciclo principal del bot"""
        logging.info(f"🚀 Iniciando bot para {self.symbol} | Timeframe: {self.timeframe}")
        
        try:
            while True:
                cycle_start = time.time()
                
                try:
                    # 1. Obtener y procesar datos
                    df = self.get_market_data()
                    df = self.calculate_indicators(df)
                    
                    # 2. Verificar señales de entrada/salida
                    signal = self.check_entry_signal(df)
                    if signal and not self.current_position:
                        logging.info(f"🎯 Señal de {signal.upper()} detectada")
                        self.execute_trade(signal)
                    
                    # 3. Esperar hasta el próximo ciclo
                    elapsed = time.time() - cycle_start
                    sleep_time = max(300 - elapsed, 10)  # 5 minutos (300 segundos)
                    logging.info(f"⏳ Próximo análisis en {sleep_time:.1f} segundos...")
                    time.sleep(sleep_time)
                    
                except ccxt.NetworkError as e:
                    logging.warning(f"🌐 Error de red: {e} | Reintentando en 60s")
                    time.sleep(60)
                except ccxt.ExchangeError as e:
                    logging.error(f"💱 Error de exchange: {e} | Reintentando en 120s")
                    time.sleep(120)
                except Exception as e:
                    logging.error(f"⚠️ Error inesperado: {e} | Reintentando en 60s")
                    time.sleep(60)
                    
        except KeyboardInterrupt:
            logging.info("🛑 Bot detenido manualmente")
            if self.current_position:
                self.execute_trade('sell' if self.current_position == 'buy' else 'buy')

# ==================== 🏁 INICIO ====================
if __name__ == "__main__":
    # Configuración de logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('eth_scalper.log'),
            logging.StreamHandler()
        ]
    )
    
    try:
        logging.info("=== BOT DE SCALPING ETH/USDT ===")
        logging.info(f"🔧 Modo: {'PRUEBA' if TEST_MODE else 'REAL'}")
        
        # Inicializar bot
        bot = EthereumScalper(api_key=API_KEY, secret_key=API_SECRET)
        
        if TEST_MODE:
            bot.exchange.set_sandbox_mode(True)
            logging.warning("⚠️ MODO PRUEBA ACTIVADO - Usando Binance Testnet")
        
        # Iniciar bot
        bot.run()
        
    except Exception as e:
        logging.critical(f"💥 Error fatal al iniciar: {e}")