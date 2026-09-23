"""Japanese prefecture choices for GUI route initialization only.

Coordinates are approximate prefectural-office positions in decimal degrees.
They are navigation defaults, not geological evidence and never select a
lithology sequence. Users may edit the resulting coordinate before execution.
"""
from __future__ import annotations

PREFECTURE_OFFICE_POINTS = {
    "北海道": (141.3479, 43.0642), "青森県": (140.7400, 40.8244),
    "岩手県": (141.1527, 39.7036), "宮城県": (140.8721, 38.2688),
    "秋田県": (140.1024, 39.7186), "山形県": (140.3633, 38.2404),
    "福島県": (140.4676, 37.7503), "茨城県": (140.4468, 36.3418),
    "栃木県": (139.8836, 36.5657), "群馬県": (139.0608, 36.3912),
    "埼玉県": (139.6489, 35.8570), "千葉県": (140.1233, 35.6047),
    "東京都": (139.6917, 35.6895), "神奈川県": (139.6425, 35.4478),
    "新潟県": (139.0232, 37.9026), "富山県": (137.2113, 36.6953),
    "石川県": (136.6256, 36.5947), "福井県": (136.2216, 36.0652),
    "山梨県": (138.5684, 35.6642), "長野県": (138.1812, 36.6513),
    "岐阜県": (136.7223, 35.3912), "静岡県": (138.3831, 34.9769),
    "愛知県": (136.9066, 35.1802), "三重県": (136.5086, 34.7303),
    "滋賀県": (135.8686, 35.0045), "京都府": (135.7681, 35.0116),
    "大阪府": (135.5197, 34.6863), "兵庫県": (135.1830, 34.6913),
    "奈良県": (135.8328, 34.6851), "和歌山県": (135.1675, 34.2260),
    "鳥取県": (134.2383, 35.5039), "島根県": (133.0505, 35.4723),
    "岡山県": (133.9344, 34.6618), "広島県": (132.4596, 34.3966),
    "山口県": (131.4706, 34.1861), "徳島県": (134.5593, 34.0658),
    "香川県": (134.0434, 34.3401), "愛媛県": (132.7657, 33.8416),
    "高知県": (133.5311, 33.5597), "福岡県": (130.4181, 33.6064),
    "佐賀県": (130.2988, 33.2494), "長崎県": (129.8737, 32.7448),
    "熊本県": (130.7417, 32.7898), "大分県": (131.6126, 33.2382),
    "宮崎県": (131.4239, 31.9111), "鹿児島県": (130.5581, 31.5602),
    "沖縄県": (127.6811, 26.2124),
}

PREFECTURE_NAMES = tuple(PREFECTURE_OFFICE_POINTS)


def representative_point(prefecture: str) -> tuple[float, float]:
    """Return a GUI navigation point; never a geology authorization."""
    try:
        return PREFECTURE_OFFICE_POINTS[prefecture]
    except KeyError as error:
        raise ValueError("unknown Japanese prefecture") from error
