"""
天气查询工具 - 使用 OpenWeatherMap API
"""

import os
import urllib.parse
import urllib.request
import json
from .base import Tool, ToolResult


class WeatherTool(Tool):
    """天气查询工具 - 通过 OpenWeatherMap API"""

    name = "weather"
    description = "查询当前天气和未来天气预报。可输入城市名称，或传入经纬度定位。"
    
    parameters = {
        "type": "object",
        "properties": {
            "city": {
                "type": "string",
                "description": "城市名称（中文或英文），如 'beijing'、'上海'"
            },
            "lat": {
                "type": "number",
                "description": "纬度，例如 39.9042"
            },
            "lon": {
                "type": "number",
                "description": "经度，例如 116.4074"
            },
            "auto_locate": {
                "type": "boolean",
                "description": "未提供城市或经纬度时，是否尝试按当前公网IP自动定位"
            },
            "reasoning": {
                "type": "string",
                "description": "为什么查询天气"
            }
        },
        "anyOf": [
            {"required": ["city"]},
            {"required": ["lat", "lon"]}
        ]
    }

    def __init__(self):
        super().__init__()
        self.api_key = os.getenv("OPENWEATHER_API_KEY")
        self.current_url = "https://api.openweathermap.org/data/2.5/weather"
        self.forecast_url = "https://api.openweathermap.org/data/2.5/forecast"
        self.reverse_geo_url = "https://api.openweathermap.org/geo/1.0/reverse"
        self.direct_geo_url = "https://api.openweathermap.org/geo/1.0/direct"
        self.geo_ip_url = "http://ip-api.com/json/?lang=zh-CN"

    def execute(
        self,
        city: str = "",
        lat: float = None,
        lon: float = None,
        auto_locate: bool = False,
        reasoning: str = "",
        **kwargs,
    ) -> ToolResult:
        """
        查询天气预报
        
        Args:
            city: 城市名称
            lat/lon: 经纬度
            auto_locate: 自动定位
            reasoning: 查询原因
        """
        if self.api_key == "YOUR_API_KEY_HERE":
            return ToolResult(
                success=False,
                content="",
                error="未配置 OpenWeatherMap API Key。请到 https://openweathermap.org/api 注册并获取免费 API Key，然后在项目根目录 .env 文件中设置 OPENWEATHER_API_KEY"
            )

        try:
            resolved = self._resolve_location(city=city, lat=lat, lon=lon, auto_locate=auto_locate)
            if not resolved.get("success"):
                return ToolResult(success=False, content="", error=resolved.get("error", "定位失败"))

            params = {
                "appid": self.api_key,
                "units": "metric",
                "lang": "zh_cn",
                "lat": resolved["lat"],
                "lon": resolved["lon"],
            }

            current_data = self._fetch_json(self.current_url, params)
            forecast_data = self._fetch_json(self.forecast_url, params)

            if str(current_data.get("cod")) not in {"200", "200.0"}:
                error_msg = current_data.get("message", "未知错误")
                return ToolResult(success=False, content="", error=f"当前天气查询失败: {error_msg}")

            if str(forecast_data.get("cod")) not in {"200", "200.0"}:
                error_msg = forecast_data.get("message", "未知错误")
                return ToolResult(success=False, content="", error=f"天气预报查询失败: {error_msg}")

            city_name = (
                current_data.get("name")
                or forecast_data.get('city', {}).get('name')
                or resolved.get("city")
                or "当前位置"
            )
            country = current_data.get('sys', {}).get('country', '') or forecast_data.get('city', {}).get('country', '')
            forecast_text = self._format_weather_summary(current_data, forecast_data, city_name=city_name, country=country)

            return ToolResult(
                success=True,
                content=forecast_text,
                metadata={
                    'city': city_name,
                    'country': country,
                    'lat': current_data.get('coord', {}).get('lat', resolved.get("lat")),
                    'lon': current_data.get('coord', {}).get('lon', resolved.get("lon")),
                    'reasoning': reasoning,
                    'auto_located': resolved.get("auto_located", False),
                }
            )

        except urllib.error.HTTPError as e:
            if e.code == 401:
                return ToolResult(
                    success=False,
                    content="",
                    error="API Key 无效或已过期，请检查 OpenWeatherMap API Key"
                )
            elif e.code == 404:
                return ToolResult(
                    success=False,
                    content="",
                    error=f"未找到城市「{city}」，请检查城市名称是否正确"
                )
            else:
                return ToolResult(
                    success=False,
                    content="",
                    error=f"HTTP 错误: {e.code}"
                )
        except urllib.error.URLError as e:
            return ToolResult(
                success=False,
                content="",
                error=f"网络错误: {str(e)}"
            )
        except Exception as e:
            return ToolResult(
                success=False,
                content="",
                error=f"查询异常: {str(e)}"
            )

    def _fetch_json(self, base_url: str, params: dict) -> dict:
        query = urllib.parse.urlencode(params)
        url = f"{base_url}?{query}"
        req = urllib.request.Request(
            url,
            headers={'User-Agent': 'QQPet-AI-Agent/1.0'}
        )
        with urllib.request.urlopen(req, timeout=10) as response:
            return json.loads(response.read().decode('utf-8'))

    def _resolve_location(self, city: str = "", lat: float = None, lon: float = None, auto_locate: bool = False) -> dict:
        if city:
            try:
                direct = self._fetch_json(
                    self.direct_geo_url,
                    {"q": city, "limit": 1, "appid": self.api_key},
                )
                if direct:
                    item = direct[0]
                    resolved_city = item.get("local_names", {}).get("zh", "") or item.get("name", "") or city
                    return {
                        "success": True,
                        "city": resolved_city,
                        "lat": item.get("lat"),
                        "lon": item.get("lon"),
                        "auto_located": False,
                    }
                return {"success": False, "error": f"未找到城市「{city}」"}
            except Exception as e:
                return {"success": False, "error": f"城市解析失败: {e}"}

        if lat is not None and lon is not None:
            resolved_city = ""
            try:
                reverse = self._fetch_json(
                    self.reverse_geo_url,
                    {"lat": lat, "lon": lon, "limit": 1, "appid": self.api_key},
                )
                if reverse:
                    item = reverse[0]
                    resolved_city = item.get("local_names", {}).get("zh", "") or item.get("name", "")
            except Exception:
                resolved_city = ""
            return {"success": True, "city": resolved_city, "lat": lat, "lon": lon, "auto_located": False}

        if auto_locate:
            try:
                req = urllib.request.Request(self.geo_ip_url, headers={'User-Agent': 'QQPet-AI-Agent/1.0'})
                with urllib.request.urlopen(req, timeout=8) as response:
                    geo = json.loads(response.read().decode('utf-8'))
                if geo.get("status") == "success":
                    return {
                        "success": True,
                        "city": geo.get("city", ""),
                        "lat": geo.get("lat"),
                        "lon": geo.get("lon"),
                        "auto_located": True,
                    }
            except Exception as e:
                return {"success": False, "error": f"自动定位失败: {e}"}

        return {"success": False, "error": "请提供城市名称，或提供经纬度，或开启自动定位"}

    def _format_weather_summary(self, current_data: dict, forecast_data: dict, city_name: str, country: str = "") -> str:
        """格式化当前天气 + 未来预报为易读文本"""
        location = f"{city_name}, {country}" if country else city_name

        current_main = current_data.get("main", {})
        current_weather = (current_data.get("weather") or [{}])[0]
        current_wind = current_data.get("wind", {})

        now_desc = current_weather.get("description", "")
        now_temp = current_main.get("temp", 0)
        feels_like = current_main.get("feels_like", now_temp)
        humidity = current_main.get("humidity", 0)
        wind_speed = current_wind.get("speed", 0)

        lines = [f"📍 {location} 天气提醒\n"]
        lines.append("=" * 30)
        lines.append(
            f"现在：{now_desc}，{now_temp:.0f}°C"
            f"（体感 {feels_like:.0f}°C，湿度 {humidity}% ，风速 {wind_speed:.1f}m/s）"
        )
        lines.append("")

        # 5天预报，每3小时一条数据，取每天12:00的数据
        daily_data = {}
        for item in forecast_data.get('list', []):
            dt = item.get('dt', 0)
            from datetime import datetime
            dt_obj = datetime.fromtimestamp(dt)
            date_str = dt_obj.strftime('%m/%d')

            if dt_obj.hour in (12, 15) and date_str not in daily_data:
                daily_data[date_str] = item

        for i, (date_str, item) in enumerate(daily_data.items()):
            if i >= 5:
                break

            main = item.get('main', {})
            weather = item.get('weather', [{}])[0]

            temp_min = main.get('temp_min', 0)
            temp_max = main.get('temp_max', 0)
            humidity = main.get('humidity', 0)
            desc = weather.get('description', '')
            icon = weather.get('icon', '')

            # 天气图标映射
            icon_map = {
                '01': '☀️', '02': '⛅', '03': '☁️', '04': '☁️',
                '09': '🌧️', '10': '🌧️', '11': '⛈️', '13': '❄️', '50': '🌫️'
            }
            icon_char = icon_map.get(icon[:2], '🌡️')

            day_names = ['今天', '明天', '后天', '大后天', '大大后天']
            day_name = day_names[i] if i < len(day_names) else date_str

            lines.append(
                f"{icon_char} {day_name}({date_str}) | {desc}\n"
                f"   🌡️ {temp_min:.0f}~{temp_max:.0f}°C | 💧 湿度 {humidity}%"
            )

        return '\n'.join(lines)
