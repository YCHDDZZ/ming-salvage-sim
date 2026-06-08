from ming_sim.simulation import filter_unmentioned_personnel_changes


def test_filter_unmentioned_personnel_changes_keeps_only_text_mentions():
    extracted = {
        "character_status_changes": [
            {"name": "王体乾", "status": "下狱", "reason": "诏书明文"},
            {"name": "张瑞图", "status": "下狱", "reason": "模型补推"},
        ],
        "office_changes": [
            {"name": "孙传庭", "new_office": "陕西总督", "reason": "邸报明文"},
            {"name": "来宗道", "new_office": "礼部尚书", "reason": "盘面误推"},
        ],
        "character_power_changes": [
            {"name": "祖大寿", "new_power": "houjin", "reason": "邸报明文"},
            {"name": "范文程", "new_power": "ming", "reason": "史实误推"},
        ],
        "secret_order_updates": [{"order_id": 3, "sim_note": "查至魏党商号"}],
    }

    cleaned = filter_unmentioned_personnel_changes(
        extracted,
        decree_text="着王体乾下狱。",
        narrative="孙传庭擢陕西总督。祖大寿降后金。",
    )

    assert cleaned["character_status_changes"] == [
        {"name": "王体乾", "status": "下狱", "reason": "诏书明文"}
    ]
    assert cleaned["office_changes"] == [
        {"name": "孙传庭", "new_office": "陕西总督", "reason": "邸报明文"}
    ]
    assert cleaned["character_power_changes"] == [
        {"name": "祖大寿", "new_power": "houjin", "reason": "邸报明文"}
    ]
    assert cleaned["secret_order_updates"] == [{"order_id": 3, "sim_note": "查至魏党商号"}]
