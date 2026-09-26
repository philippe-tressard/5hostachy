"""Coupure ordinaire ou blocage possible du compte WhatsApp (#1061).

La boucle ordinaire (428, ~4 h 45) se rétablit en minutes et ne doit pas crier
au blocage ; un 401/403 venus de WhatsApp, ou une déconnexion qui dure, si.
"""

from __future__ import annotations

from app.utils.health_monitor import _heures_depuis
from app.utils.verdict_whatsapp import SEUIL_DURABLE_H, verdict_whatsapp


def test_connecte_rien_a_dire():
    assert verdict_whatsapp("open", None, 401) is None


def test_la_coupure_ordinaire_reste_ordinaire():
    v = verdict_whatsapp("disconnected", 0.1, 428)
    assert "Reconnexion requise" in v and "BLOQUÉ" not in v


def test_un_401_ou_403_dit_le_blocage_possible():
    for code in (401, 403):
        v = verdict_whatsapp("disconnected", 0.1, code)
        assert "BLOQUÉ" in v and f"code {code}" in v and "courriel" in v


def test_une_deconnexion_qui_dure_n_est_plus_ordinaire():
    v = verdict_whatsapp("connecting", SEUIL_DURABLE_H + 1, 428)
    assert "hors ligne depuis" in v and "Conduite à tenir" in v


def test_cas_zero_sans_duree_connue_on_reste_prudent_mais_ordinaire():
    assert "Reconnexion requise" in verdict_whatsapp("disconnected", None, None)


def test_la_duree_se_lit_sur_l_horodatage_du_bridge():
    from datetime import timedelta, timezone

    from app.utils import horloge

    il_y_a_7h = (horloge.maintenant() - timedelta(hours=7)).replace(tzinfo=timezone.utc)
    assert 6.9 < _heures_depuis(il_y_a_7h.isoformat().replace("+00:00", "Z")) < 7.1
    assert _heures_depuis(None) is None and _heures_depuis("n'importe quoi") is None
