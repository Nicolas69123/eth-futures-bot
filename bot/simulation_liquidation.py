#!/usr/bin/env python3
"""
Simulation de Liquidation en Cross Margin
Calcule à quel niveau de crash vous seriez liquidé
"""

# Configuration
CAPITAL_INITIAL = 100  # 100€ de capital
MARGIN_INITIAL = 0.05  # 0.05€ par position (0.10€ total pour le hedge)
LEVERAGE = 50          # Leverage 50x
TP_PERCENT = 0.5       # TP à 0.5%
FIRST_FIBO = 0.8       # Premier niveau Fibonacci à 0.8%

def calculate_liquidation():
    print("="*80)
    print("SIMULATION LIQUIDATION - CROSS MARGIN")
    print("="*80)
    print(f"Capital: {CAPITAL_INITIAL}€")
    print(f"Position initiale: {MARGIN_INITIAL:.2f}€ LONG + {MARGIN_INITIAL:.2f}€ SHORT")
    print(f"Leverage: {LEVERAGE}x")
    print(f"TP: {TP_PERCENT}%")
    print(f"Premier Fibo: {FIRST_FIBO}%")
    print("="*80)
    print()

    # Niveaux Fibonacci progressifs (chaque niveau double la distance)
    fibo_levels = []
    level = FIRST_FIBO
    for i in range(10):  # Max 10 niveaux
        fibo_levels.append(level)
        level = level * 2  # Progression: 0.8%, 1.6%, 3.2%, 6.4%...

    print("NIVEAUX FIBONACCI CALCULÉS:")
    for i, level in enumerate(fibo_levels[:6]):
        print(f"  Fibo {i+1}: -{level:.1f}%")
    print()

    # Simulation de crash progressif
    capital_used = MARGIN_INITIAL * 2  # Initial: 10€
    margin_long = MARGIN_INITIAL
    margin_short = MARGIN_INITIAL

    print("SIMULATION DE CRASH PROGRESSIF:")
    print("-"*80)

    for i, fibo_level in enumerate(fibo_levels):
        # Le LONG double à ce niveau
        margin_long *= 2
        total_margin = margin_long + margin_short

        # Calcul PnL
        # LONG perd quand le prix baisse
        pnl_long = -(margin_long * LEVERAGE * fibo_level / 100)
        # SHORT gagne quand le prix baisse
        pnl_short = margin_short * LEVERAGE * fibo_level / 100
        pnl_net = pnl_long + pnl_short

        # Capital nécessaire (marge + pertes à couvrir)
        capital_needed = total_margin + abs(pnl_net)

        print(f"NIVEAU {i+1}: Prix -{fibo_level:.1f}%")
        print(f"  • LONG: {margin_long:.2f}€ de marge → PnL: {pnl_long:.2f}€")
        print(f"  • SHORT: {margin_short:.2f}€ de marge → PnL: +{pnl_short:.2f}€")
        print(f"  • PnL Net: {pnl_net:.1f}€")
        print(f"  • Capital total nécessaire: {capital_needed:.1f}€")

        if capital_needed > CAPITAL_INITIAL:
            print(f"  💥 LIQUIDATION! Capital insuffisant ({CAPITAL_INITIAL}€ < {capital_needed:.1f}€)")
            print()
            print("="*80)
            print(f"📊 RÉSULTAT FINAL:")
            print(f"  • Vous seriez liquidé à -{fibo_level:.1f}% de crash")
            print(f"  • Après {i+1} niveaux Fibonacci touchés")
            print(f"  • Avec un LONG de {margin_long:.2f}€ de marge")
            print("="*80)
            return fibo_level

        print(f"  ✅ Survivable (Capital restant: {CAPITAL_INITIAL - capital_needed:.1f}€)")
        print()

    print("✅ Vous survivez à tous les niveaux testés!")
    return None

def calculate_with_different_configs():
    """Test avec différentes configurations"""
    print("\n" + "="*80)
    print("COMPARAISON DE CONFIGURATIONS")
    print("="*80)

    configs = [
        {"name": "Conservative", "first_fibo": 1.2, "progression": 1.5},
        {"name": "Standard", "first_fibo": 0.8, "progression": 2.0},
        {"name": "Aggressive", "first_fibo": 0.5, "progression": 2.0},
        {"name": "Very Aggressive", "first_fibo": 0.3, "progression": 2.0}
    ]

    for config in configs:
        print(f"\n{config['name']} (Premier: {config['first_fibo']}%, Progression: x{config['progression']}):")

        # Calcul rapide
        capital = CAPITAL_INITIAL
        margin = MARGIN_INITIAL
        level = config['first_fibo']

        for i in range(10):
            margin_long = MARGIN_INITIAL * (2 ** (i+1))  # Double à chaque niveau
            margin_short = MARGIN_INITIAL
            total_margin = margin_long + margin_short

            # PnL approximatif
            pnl_long = -(margin_long * LEVERAGE * level / 100)
            pnl_short = margin_short * LEVERAGE * level / 100
            capital_needed = total_margin + abs(pnl_long + pnl_short)

            if capital_needed > CAPITAL_INITIAL:
                print(f"  → Liquidation à -{level:.1f}% après {i+1} doublements")
                break

            level *= config['progression']

    print("\n" + "="*80)

if __name__ == "__main__":
    # Simulation principale
    liquidation_level = calculate_liquidation()

    # Comparaison de configurations
    calculate_with_different_configs()

    # Recommandation
    print("\n📌 RECOMMANDATION:")
    print(f"Avec 100€ de capital et position initiale de {MARGIN_INITIAL*2:.2f}€:")
    print("• Configuration SAFE: Premier Fibo à 1.2%, progression x1.5")
    print("• Configuration STANDARD: Premier Fibo à 0.8%, progression x2")
    print("• Configuration AGGRESSIVE: Premier Fibo à 0.5%, progression x2")
    print("\nVotre choix dépend de votre tolérance au risque!")