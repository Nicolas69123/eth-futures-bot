#!/usr/bin/env python3
"""
🧹 Cleanup Complet - Script Robuste

Nettoie TOUTES les positions et ordres sur toutes les paires.
Vérifie en boucle jusqu'à ce que TOUT soit fermé.

Usage:
    python cleanup_complete.py
    python cleanup_complete.py --pair DOGE/USDT:USDT --api-key-id 1
"""

import ccxt
import os
import time
import argparse
from dotenv import load_dotenv

load_dotenv()


def cleanup_pair(exchange, pair, pair_name, max_attempts=5):
    """
    Cleanup une paire spécifique avec vérification

    Returns:
        bool: True si clean, False si échec après max_attempts
    """
    symbol_bitget = pair.replace('/USDT:USDT', 'USDT')

    for attempt in range(max_attempts):
        print(f"\n{'='*60}")
        print(f"🔄 {pair_name} - Tentative {attempt + 1}/{max_attempts}")
        print(f"{'='*60}")

        try:
            # 1. Annuler TOUS les ordres LIMIT
            print(f"[1/3] Annulation ordres LIMIT...")
            orders = exchange.fetch_open_orders(pair)
            if orders:
                print(f"  📝 {len(orders)} ordres LIMIT à annuler")
                for order in orders:
                    try:
                        exchange.cancel_order(order['id'], pair)
                        print(f"    ✅ Ordre {order['id'][:12]}... annulé")
                        time.sleep(0.3)
                    except Exception as e:
                        if '40721' not in str(e):  # Order already cancelled
                            print(f"    ⚠️  Erreur: {str(e)[:50]}")
            else:
                print(f"  ✅ Aucun ordre LIMIT")

            time.sleep(1)

            # 2. Annuler TOUS les ordres TP/SL (plan orders)
            print(f"\n[2/3] Annulation ordres TP/SL...")
            try:
                for plan_type in ['pos_profit', 'pos_loss']:
                    tpsl_orders = exchange.private_mix_get_v2_mix_order_orders_plan_pending({
                        'symbol': symbol_bitget,
                        'productType': 'USDT-FUTURES',
                        'planType': plan_type
                    })

                    if tpsl_orders.get('code') == '00000':
                        orders_list = tpsl_orders.get('data', {}).get('entrustedList', [])
                        if orders_list:
                            print(f"  📝 {len(orders_list)} ordres TP/SL ({plan_type})")
                            for order in orders_list:
                                try:
                                    exchange.private_mix_post_v2_mix_order_cancel_plan_order({
                                        'orderId': order['orderId'],
                                        'symbol': symbol_bitget,
                                        'productType': 'USDT-FUTURES',
                                        'marginCoin': 'USDT'
                                    })
                                    print(f"    ✅ TP/SL {order['orderId'][:12]}... annulé")
                                    time.sleep(0.3)
                                except Exception as e:
                                    print(f"    ⚠️  Erreur: {str(e)[:50]}")

                print(f"  ✅ Ordres TP/SL nettoyés")
            except Exception as e:
                print(f"  ⚠️  TP/SL cleanup: {str(e)[:50]}")

            time.sleep(1)

            # 3. Fermer TOUTES les positions (Flash Close)
            print(f"\n[3/3] Fermeture positions...")
            positions = exchange.fetch_positions([pair])

            positions_to_close = [p for p in positions if float(p.get('contracts', 0)) > 0]

            if positions_to_close:
                print(f"  📊 {len(positions_to_close)} positions à fermer")
                for pos in positions_to_close:
                    side = pos.get('side', '').lower()
                    size = float(pos.get('contracts', 0))
                    print(f"    🔴 Flash Close {side.upper()}: {size:.0f} contrats...")

                    try:
                        result = exchange.private_mix_post_v2_mix_order_close_positions({
                            'symbol': symbol_bitget,
                            'productType': 'USDT-FUTURES',
                            'holdSide': side
                        })

                        if result.get('code') == '00000':
                            print(f"      ✅ Flash Close OK")
                        else:
                            print(f"      ⚠️  Résultat: {result.get('msg', '')}")

                        time.sleep(1)

                    except Exception as e:
                        # Si flash close échoue, essayer MARKET order
                        if '22002' in str(e):
                            print(f"      ⚠️  Position déjà fermée (ignorer)")
                        else:
                            print(f"      ⚠️  Flash close échec: {str(e)[:40]}")
                            try:
                                market_side = 'sell' if side == 'long' else 'buy'
                                exchange.create_order(pair, 'market', market_side, size,
                                                     params={'tradeSide': 'close', 'holdSide': side})
                                print(f"      ✅ Market close OK")
                                time.sleep(1)
                            except:
                                print(f"      ❌ Market close échec aussi")
            else:
                print(f"  ✅ Aucune position")

            # 4. VÉRIFICATION FINALE
            print(f"\n{'='*60}")
            print(f"🔍 VÉRIFICATION {pair_name}")
            print(f"{'='*60}")

            time.sleep(3)  # Attendre que tout soit bien propagé

            final_orders = exchange.fetch_open_orders(pair)
            final_positions = exchange.fetch_positions([pair])
            final_pos_count = sum(1 for p in final_positions if float(p.get('contracts', 0)) > 0)

            print(f"  Ordres LIMIT: {len(final_orders)}")
            print(f"  Positions: {final_pos_count}")

            if len(final_orders) == 0 and final_pos_count == 0:
                print(f"  ✅ {pair_name} 100% CLEAN!")
                return True
            else:
                print(f"  ⚠️  Pas clean: {len(final_orders)} ordres, {final_pos_count} positions")
                if attempt < max_attempts - 1:
                    print(f"  🔄 Nouvelle tentative dans 3s...")
                    time.sleep(3)
                    continue

        except Exception as e:
            print(f"❌ Erreur tentative {attempt + 1}: {e}")
            if attempt < max_attempts - 1:
                time.sleep(3)
                continue

    # Échec après toutes les tentatives
    print(f"\n❌ {pair_name}: CLEANUP INCOMPLET après {max_attempts} tentatives!")
    return False


def main():
    parser = argparse.ArgumentParser(description='Cleanup complet toutes paires')
    parser.add_argument('--pair', help='Paire spécifique (optionnel)', default=None)
    parser.add_argument('--api-key-id', type=int, choices=[1, 2], default=None,
                        help='API Key ID (1 ou 2)')

    args = parser.parse_args()

    # Déterminer les paires à nettoyer
    if args.pair:
        # Une seule paire
        pairs = [(args.pair, args.api_key_id or 1)]
    else:
        # Toutes les paires (4)
        pairs = [
            ('DOGE/USDT:USDT', 1),
            ('SHIB/USDT:USDT', 1),
            ('PEPE/USDT:USDT', 2),
            ('ETH/USDT:USDT', 2),
        ]

    # Initialiser exchanges
    exchange1 = ccxt.bitget({
        'apiKey': os.getenv('BITGET_API_KEY'),
        'secret': os.getenv('BITGET_SECRET'),
        'password': os.getenv('BITGET_PASSPHRASE'),
        'options': {'defaultType': 'swap'},
        'headers': {'PAPTRADING': '1'},
        'enableRateLimit': True
    })

    exchange2 = ccxt.bitget({
        'apiKey': os.getenv('BITGET_API_KEY_2'),
        'secret': os.getenv('BITGET_SECRET_2'),
        'password': os.getenv('BITGET_PASSPHRASE_2'),
        'options': {'defaultType': 'swap'},
        'headers': {'PAPTRADING': '1'},
        'enableRateLimit': True
    })

    print("=" * 80)
    print("🧹 CLEANUP COMPLET ROBUSTE")
    print("=" * 80)
    print(f"\nPaires à nettoyer: {len(pairs)}")
    for p, k in pairs:
        print(f"  • {p.split('/')[0]} (API Key {k})")
    print()

    # Cleanup chaque paire
    results = {}
    for pair, api_key_id in pairs:
        exchange = exchange1 if api_key_id == 1 else exchange2
        pair_name = pair.split('/')[0]

        result = cleanup_pair(exchange, pair, pair_name)
        results[pair_name] = result

        time.sleep(2)  # Délai entre paires

    # Résumé final
    print("\n" + "=" * 80)
    print("📊 RÉSUMÉ FINAL CLEANUP")
    print("=" * 80)

    all_clean = True
    for pair_name, success in results.items():
        status = "✅" if success else "❌"
        print(f"{status} {pair_name}: {'CLEAN' if success else 'ÉCHEC'}")
        if not success:
            all_clean = False

    print("=" * 80)

    if all_clean:
        print("🎉 TOUT EST 100% CLEAN!")
        print("✅ Vous pouvez lancer les bots maintenant")
        return 0
    else:
        print("❌ CLEANUP INCOMPLET - Vérifiez manuellement")
        return 1


if __name__ == '__main__':
    exit(main())
