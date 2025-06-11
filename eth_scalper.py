#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
BOT DE SCALPING PARA ETH/USDT EN BINANCE FUTURES
Versión: 2.0
Autor: Serge12
"""

# ==================== 📦 IMPORTACIONES ====================
import ccxt          # type: ignore # Conexión con exchanges (Binance)
import pandas as pd  # Manipulación de datos
import time          # Control de tiempos y esperas
from datetime import datetime  # type: ignore # Manejo de fechas/horas
import logging       # Sistema de registro de operaciones

# ==================== ⚙️ CONFIGURACIÓN INICIAL ====================
# 🔄 CAMBIA ESTOS VALORES PARA TU CONFIGURACIÓN PERSONALIZADA
API_KEY = "TU_API_KEY_AQUI"       # 👈 Reemplaza con tu API Key de Binance
API_SECRET = "TU_SECRET_KEY_AQUI" # 👈 Reemplaza con tu Secret Key
TEST_MODE = True                  # 👈 True para pruebas, False para real

# ==================== 🤖 CLASE PRINCIPAL DEL BOT ====================
class EthereumScalper:
    def __init__(self, api_key: str, secret_key: str):
        """
        Inicializa el bot con credenciales de Binance
        🔄 CAMBIA LOS PARÁMETROS DE TRADING AQUÍ:
        """
        # Configuración del exchange
        self.exchange = ccxt.binance({ # type: ignore
            'apiKey': api_key,
            'secret': secret_key,
            'enableRateLimit': True,
            'options': {'defaultType': 'future'}  # Trading de futuros
        })
        
        # 🔄 PARÁMETROS AJUSTABLES - MODIFICA ESTOS VALORES:
        self.symbol = 'ETH/USDT'      # 👈 Par a operar (ej: 'BTC/USDT')
        self.timeframe = '5m'         # 👈 Intervalo (1m, 5m, 15m, etc.)
        self.amount = 0.05            # 👈 Cantidad de ETH por operación
        self.leverage = 10            # 👈 Apalancamiento (1-125x)
        self.stop_loss = 0.008        # 👈 0.8% de stop loss (0.008 = 0.8%)
        self.take_profit = 0.015      # 👈 1.5% de take profit
        
        # 🔄 PARÁMETROS DE ESTRATEGIA - AJUSTA SEGÚN TU ESTILO:
        self.ema_fast = 8             # 👈 EMA rápida (9 para BTC)
        self.ema_slow = 20            # 👈 EMA lenta (21 para BTC)
        self.rsi_period = 12          # 👈 Periodo RSI (14 es estándar)
        self.rsi_overbought = 68       # 👈 Nivel sobrecompra
        self.rsi_oversold = 32         # 👈 Nivel sobreventa
        
        # Variables de estado (no modificar)
        self.current_position = None
        self.setup()

    def setup(self):
        """Configura el mercado y el apalancamiento"""
        try:
            self.exchange.load_markets() # type: ignore
            self.exchange.set_leverage(self.leverage, self.symbol) # type: ignore
            self.exchange.set_margin_mode('cross', self.symbol) # type: ignore
            logging.info(f"✅ Bot configurado para {self.symbol} | Apalancamiento: {self.leverage}x")
        except Exception as e:
            logging.error(f"❌ Error en configuración: {e}")
            raise

    # ==================== 📊 ANÁLISIS DE MERCADO ====================
    def get_market_data(self):
        """Obtiene datos OHLCV del mercado"""
        try:
            ohlcv = self.exchange.fetch_ohlcv( # type: ignore
                self.symbol, 
                self.timeframe, 
                limit=100  # 🔄 Ajusta cantidad de velas históricas
            )
            df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume']) # type: ignore
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms') # type: ignore
            df.set_index('timestamp', inplace=True) # type: ignore
            return df
        except Exception as e:
            logging.error(f"❌ Error obteniendo datos: {e}")
            raise

    def calculate_indicators(self, df: pd.DataFrame):
        """
        Calcula indicadores técnicos
        🔄 PUEDES AÑADIR MÁS INDICADORES AQUÍ:
        """
        try:
            # EMA (Medias Móviles Exponenciales)
            df['ema_fast'] = df['close'].ewm(span=self.ema_fast, adjust=False).mean()
            df['ema_slow'] = df['close'].ewm(span=self.ema_slow, adjust=False).mean()
            
            # RSI (Índice de Fuerza Relativa)
            delta = df['close'].diff()
            gain = (delta.where(delta > 0, 0)).ewm(alpha=1/self.rsi_period, adjust=False).mean()
            loss = (-delta.where(delta < 0, 0)).ewm(alpha=1/self.rsi_period, adjust=False).mean()
            rs = gain / loss
            df['rsi'] = 100 - (100 / (1 + rs))
            
            # 🔄 AÑADE TUS INDICADORES PERSONALIZADOS AQUÍ:
            # Ejemplo: MACD, Bollinger Bands, etc.
            
            return df
        except Exception as e:
            logging.error(f"❌ Error calculando indicadores: {e}")
            raise

    # ==================== 📈📉 ESTRATEGIA DE TRADING ====================
    def check_entry_signal(self, df: pd.DataFrame):
        """
        Detecta señales de entrada
        🔄 MODIFICA ESTA LÓGICA PARA TU ESTRATEGIA PERSONAL:
        """
        last = df.iloc[-1]  # Última vela
        prev = df.iloc[-2]  # Vela anterior
        
        # Señal de COMPRA (EMA rápida cruza arriba de la lenta + RSI no sobrecomprado)
        buy_condition = (
            (last['ema_fast'] > last['ema_slow']) and 
            (prev['ema_fast'] <= prev['ema_slow']) and 
            (last['rsi'] < self.rsi_overbought)
        )
        
        # Señal de VENTA (EMA rápida cruza abajo de la lenta + RSI no sobrevendido)
        sell_condition = (
            (last['ema_fast'] < last['ema_slow']) and 
            (prev['ema_fast'] >= prev['ema_slow']) and 
            (last['rsi'] > self.rsi_oversold)
        )
        
        if buy_condition:
            return 'buy'
        elif sell_condition:
            return 'sell'
        return None

    def check_exit_signal(self, df: pd.DataFrame):
        """
        Detecta señales de salida
        🔄 AJUSTA LAS CONDICIONES DE SALIDA:
        """
        if not self.current_position:
            return False
            
        last = df.iloc[-1]
        
        # Salida para LARGOS
        if self.current_position == 'buy':
            return (
                (last['ema_fast'] < last['ema_slow']) or  # EMA cruza a la baja
                (last['rsi'] > self.rsi_overbought + 5)   # RSI muy sobrecomprado
            )
        
        # Salida para CORTOS
        elif self.current_position == 'sell':
            return (
                (last['ema_fast'] > last['ema_slow']) or  # EMA cruza al alza
                (last['rsi'] < self.rsi_oversold - 5)     # RSI muy sobrevendido
            )
        
        return False

    # ==================== 💰 EJECUCIÓN DE ÓRDENES ====================
    def execute_trade(self, signal: str):
        """
        Ejecuta órdenes en el exchange
        🔄 MODIFICA EL TIPO DE ÓRDENES AQUÍ:
        """
        try:
            price = self.exchange.fetch_ticker(self.symbol)['last']
            amount = self.amount * self.leverage
            
            logging.info(f"⚡ Señal de {signal.upper()} detectada a {price}")
            
            # Orden de mercado (ejecución inmediata)
            order = self.exchange.create_order(
                symbol=self.symbol,
                type='MARKET',  # 🔄 Cambia a 'LIMIT' para órdenes limitadas
                side=signal.upper(),
                amount=amount,
                params={'closePosition': False}
            )
            
            # Coloca Stop Loss y Take Profit
            self.place_sl_tp(signal, float(order['price']))
            
            self.current_position = signal
            return order
        except Exception as e:
            logging.error(f"❌ Error ejecutando orden: {e}")
            return None

    def place_sl_tp(self, side: str, entry_price: float):
        """
        Coloca Stop Loss y Take Profit
        🔄 AJUSTA LOS PARÁMETROS DE PROTECCIÓN:
        """
        try:
            amount = self.amount * self.leverage
            
            # Cálculo de precios
            sl_price = entry_price * (1 - self.stop_loss) if side == 'buy' else entry_price * (1 + self.stop_loss)
            tp_price = entry_price * (1 + self.take_profit) if side == 'buy' else entry_price * (1 - self.take_profit)
            
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
            logging.error(f"❌ Error colocando SL/TP: {e}")

    # ==================== 🔄 CICLO PRINCIPAL ====================
    def run(self):
        """Ejecuta el ciclo principal del bot"""
        logging.info(f"🚀 Iniciando bot para {self.symbol} en timeframe {self.timeframe}")
        
        try:
            while True:
                cycle_start = time.time()
                
                try:
                    # 1. Obtener datos de mercado
                    df = self.get_market_data()
                    df = self.calculate_indicators(df)
                    
                    # 2. Verificar si debemos salir de una posición
                    if self.current_position and self.check_exit_signal(df):
                        logging.info("⚠️ Señal de SALIDA detectada")
                        self.close_position()
                    
                    # 3. Verificar señales de entrada
                    signal = self.check_entry_signal(df)
                    if signal and not self.current_position:
                        logging.info(f"🎯 Señal de {signal.upper()} detectada")
                        self.execute_trade(signal)
                    
                    # 4. Esperar hasta el próximo ciclo
                    elapsed = time.time() - cycle_start
                    sleep_time = max(300 - elapsed, 10)  # 🔄 Ajusta el timeframe aquí
                    logging.info(f"⏳ Próximo análisis en {sleep_time:.1f}s")
                    time.sleep(sleep_time)
                    
                except Exception as e:
                    logging.error(f"🔧 Error en ciclo: {e}")
                    time.sleep(60)
                    
        except KeyboardInterrupt:
            logging.info("🛑 Bot detenido manualmente")
            if self.current_position:
                self.close_position()

# ==================== 🏁 INICIO DEL PROGRAMA ====================
if __name__ == "__main__":
    # Configuración inicial
    logging.info("=== BOT DE SCALPING ETH/USDT ===")
    
    try:
        # Inicializar bot
        bot = EthereumScalper(api_key=API_KEY, secret_key=API_SECRET)
        
        if TEST_MODE:
            logging.warning("⚠️ MODO PRUEBA ACTIVADO - No se realizan operaciones reales")
            bot.exchange.set_sandbox_mode(True)  # Usa Binance Testnet
        
        # Iniciar bot
        bot.run()
        
    except Exception as e:
        logging.error(f"💥 Error fatal: {e}")