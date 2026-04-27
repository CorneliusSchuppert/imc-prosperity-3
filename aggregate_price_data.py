import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

# Load the historical mid-price series for Squid Ink.
# Replace path below with your own copy of the IMC Prosperity 3 historical data bottle.
df = pd.read_csv('squid_ink_mid_price.csv')
df.sort_values(by='Time', inplace=True)

# Define moving average window parameters
short_window = 300  # short-term window
long_window = 100   # long-term window

# Calculate the Simple Moving Averages (SMA)
df['SMA_short'] = df['mid_price'].rolling(window=short_window, min_periods=1).mean()
df['SMA_long'] = df['mid_price'].rolling(window=long_window, min_periods=1).mean()

# Generate signals: Signal = 1 when SMA_short > SMA_long, else 0.
df['Signal'] = 0
df.loc[long_window:, 'Signal'] = np.where(
    df.loc[long_window:, 'SMA_short'] > df.loc[long_window:, 'SMA_long'],
    1,
    0
)

# Create positions by finding the difference in signals (1 => buy, -1 => sell)
df['Position'] = df['Signal'].diff()

# Plot the mid_price, SMAs, and buy/sell signals
plt.figure(figsize=(12, 6))
plt.plot(df['Time'], df['mid_price'], label='Mid Price', alpha=0.7)
plt.plot(df['Time'], df['SMA_short'], label=f'SMA {short_window}', alpha=0.8)
plt.plot(df['Time'], df['SMA_long'], label=f'SMA {long_window}', alpha=0.8)

plt.plot(df[df['Position'] == 1]['Time'],
         df[df['Position'] == 1]['mid_price'],
         '^', markersize=10, color='g', label='Buy Signal')

plt.plot(df[df['Position'] == -1]['Time'],
         df[df['Position'] == -1]['mid_price'],
         'v', markersize=10, color='r', label='Sell Signal')

plt.title('Moving Average Crossover Strategy')
plt.xlabel('Time (arbitrary integer)')
plt.ylabel('Price')
plt.legend()
plt.show()

# ----- Backtesting: Calculate Trade Profits -----

# Initialize a list to store trade details
trades = []
entry_price = None
entry_time = None

# Loop through the DataFrame to capture trades
for _, row in df.iterrows():
    # Buy signal: when Position changes to 1
    if row['Position'] == 1:
        entry_price = row['mid_price']
        entry_time = row['Time']
    # Sell signal: when Position changes to -1 and there is an open trade
    elif row['Position'] == -1 and entry_price is not None:
        exit_price = row['mid_price']
        exit_time = row['Time']
        profit = exit_price - entry_price
        trades.append({
            'Entry Time': entry_time,
            'Entry Price': entry_price,
            'Exit Time': exit_time,
            'Exit Price': exit_price,
            'Profit': profit
        })
        # Reset entry variables
        entry_price = None
        entry_time = None

# Create a DataFrame for trades and calculate total profit
trades_df = pd.DataFrame(trades)
total_profit = trades_df['Profit'].sum()

print("Trades:")
print(trades_df)
print("\nTotal Profit: ", total_profit)