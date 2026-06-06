import argparse
import json
import math
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
USER_AGENT = 'HermesAgent/1.0 (contact: hermes@agent.ai)'
DATA_SOURCE = 'OpenStreetMap/Nominatim'
NOMINATIM_SEARCH = 'https://nominatim.openstreetmap.org/search'
NOMINATIM_REVERSE = 'https://nominatim.openstreetmap.org/reverse'
OVERPASS_URLS = ['https://overpass-api.de/api/interpreter', 'https://overpass.kumi.systems/api/interpreter']
OVERPASS_API = OVERPASS_URLS[0]
OSRM_BASE = 'https://router.project-osrm.org/route/v1'
TIMEAPI_BASE = 'https://timeapi.io/api/timezone/coordinate'
NOMINATIM_RATE_LIMIT = 1.0
MAX_RETRIES = 3
RETRY_DELAY = 2.0
CATEGORY_TAGS = {'restaurant': ('amenity', 'restaurant'), 'cafe': ('amenity', 'cafe'), 'bar': ('amenity', 'bar'), 'bakery': [('shop', 'bakery'), ('amenity', 'bakery')], 'convenience_store': ('shop', 'convenience'), 'hospital': ('amenity', 'hospital'), 'pharmacy': ('amenity', 'pharmacy'), 'dentist': ('amenity', 'dentist'), 'doctor': ('amenity', 'doctors'), 'veterinary': ('amenity', 'veterinary'), 'hotel': ('tourism', 'hotel'), 'guest_house': ('tourism', 'guest_house'), 'camp_site': ('tourism', 'camp_site'), 'supermarket': ('shop', 'supermarket'), 'bookshop': ('shop', 'books'), 'laundry': ('shop', 'laundry'), 'atm': ('amenity', 'atm'), 'bank': ('amenity', 'bank'), 'gas_station': ('amenity', 'fuel'), 'parking': ('amenity', 'parking'), 'airport': ('aeroway', 'aerodrome'), 'train_station': ('railway', 'station'), 'bus_stop': ('highway', 'bus_stop'), 'taxi': ('amenity', 'taxi'), 'car_wash': ('amenity', 'car_wash'), 'car_rental': ('amenity', 'car_rental'), 'bicycle_rental': ('amenity', 'bicycle_rental'), 'museum': ('tourism', 'museum'), 'cinema': ('amenity', 'cinema'), 'theatre': ('amenity', 'theatre'), 'nightclub': ('amenity', 'nightclub'), 'zoo': ('tourism', 'zoo'), 'school': ('amenity', 'school'), 'university': ('amenity', 'university'), 'library': ('amenity', 'library'), 'police': ('amenity', 'police'), 'fire_station': ('amenity', 'fire_station'), 'post_office': ('amenity', 'post_office'), 'church': ('amenity', 'place_of_worship'), 'mosque': ('amenity', 'place_of_worship'), 'synagogue': ('amenity', 'place_of_worship'), 'park': ('leisure', 'park'), 'gym': ('leisure', 'fitness_centre'), 'swimming_pool': ('leisure', 'swimming_pool'), 'playground': ('leisure', 'playground'), 'stadium': ('leisure', 'stadium')}
RELIGION_FILTER = {'church': 'christian', 'mosque': 'muslim', 'synagogue': 'jewish'}
VALID_CATEGORIES = sorted(CATEGORY_TAGS.keys())

def _tags_for(category):
    entry = CATEGORY_TAGS[category]
    if isinstance(entry, list):
        return list(entry)
    return [entry]
OSRM_PROFILES = {'driving': 'driving', 'walking': 'foot', 'cycling': 'bike'}

def print_json(data):
    print(json.dumps(data, indent=2, ensure_ascii=False))

def error_exit(message, code=1):
    print_json({'error': message, 'status': 'error'})
    sys.exit(code)

def http_get(url, params=None, retries=MAX_RETRIES, silent=False):
    if params:
        url = url + '?' + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={'User-Agent': USER_AGENT})
    last_error = None
    for attempt in range(1, retries + 1):
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                raw = resp.read().decode('utf-8')
                return json.loads(raw)
        except urllib.error.HTTPError as exc:
            last_error = f'HTTP {exc.code}: {exc.reason} for {url}'
            if exc.code in (429, 503, 502, 504):
                time.sleep(RETRY_DELAY * attempt)
            else:
                if silent:
                    raise RuntimeError(last_error)
                error_exit(last_error)
        except urllib.error.URLError as exc:
            last_error = f'URL error: {exc.reason}'
            time.sleep(RETRY_DELAY * attempt)
        except json.JSONDecodeError as exc:
            last_error = f'JSON parse error: {exc}'
            time.sleep(RETRY_DELAY * attempt)
    msg = f'Request failed after {retries} attempts. Last error: {last_error}'
    if silent:
        raise RuntimeError(msg)
    error_exit(msg)

def http_get_text(url, params=None, retries=MAX_RETRIES, silent=False):
    if params:
        url = url + '?' + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={'User-Agent': USER_AGENT})
    last_error = None
    for attempt in range(1, retries + 1):
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                return resp.read().decode('utf-8')
        except urllib.error.HTTPError as exc:
            last_error = f'HTTP {exc.code}: {exc.reason} for {url}'
            if exc.code in (429, 503, 502, 504):
                time.sleep(RETRY_DELAY * attempt)
            else:
                if silent:
                    raise RuntimeError(last_error)
                error_exit(last_error)
        except urllib.error.URLError as exc:
            last_error = f'URL error: {exc.reason}'
            time.sleep(RETRY_DELAY * attempt)
    msg = f'Request failed after {retries} attempts. Last error: {last_error}'
    if silent:
        raise RuntimeError(msg)
    error_exit(msg)

def http_post(url, data_str, retries=MAX_RETRIES):
    encoded = data_str.encode('utf-8')
    req = urllib.request.Request(url, data=encoded, headers={'User-Agent': USER_AGENT, 'Content-Type': 'application/x-www-form-urlencoded'})
    last_error = None
    for attempt in range(1, retries + 1):
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                raw = resp.read().decode('utf-8')
                return json.loads(raw)
        except urllib.error.HTTPError as exc:
            last_error = f'HTTP {exc.code}: {exc.reason}'
            if exc.code in (429, 503, 502, 504):
                time.sleep(RETRY_DELAY * attempt)
            else:
                error_exit(last_error)
        except urllib.error.URLError as exc:
            last_error = f'URL error: {exc.reason}'
            time.sleep(RETRY_DELAY * attempt)
        except json.JSONDecodeError as exc:
            last_error = f'JSON parse error: {exc}'
            time.sleep(RETRY_DELAY * attempt)
    error_exit(f'POST failed after {retries} attempts. Last error: {last_error}')

def overpass_query(query):
    post_data = 'data=' + urllib.parse.quote(query)
    last_error = None
    for url in OVERPASS_URLS:
        try:
            return http_post(url, post_data, retries=1)
        except SystemExit:
            last_error = f'mirror {url} exhausted retries'
            continue
        except Exception as exc:
            last_error = f'{url}: {exc}'
            continue
    error_exit(f'All Overpass mirrors failed. Last error: {last_error or 'unknown'}')

def haversine_m(lat1, lon1, lat2, lon2):
    R = 6371000
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
    return 2 * R * math.atan2(math.sqrt(a), math.sqrt(1 - a))

def nominatim_search(query, limit=5):
    params = {'q': query, 'format': 'json', 'limit': limit, 'addressdetails': 1}
    time.sleep(NOMINATIM_RATE_LIMIT)
    return http_get(NOMINATIM_SEARCH, params=params)

def nominatim_reverse(lat, lon):
    params = {'lat': lat, 'lon': lon, 'format': 'json', 'addressdetails': 1}
    time.sleep(NOMINATIM_RATE_LIMIT)
    return http_get(NOMINATIM_REVERSE, params=params)

def geocode_single(query):
    results = nominatim_search(query, limit=1)
    if not results:
        error_exit(f'Could not geocode: {query}')
    r = results[0]
    return (float(r['lat']), float(r['lon']), r.get('display_name', query))

def build_overpass_nearby(tag_key, tag_val, lat, lon, radius, limit, religion=None, tag_pairs=None):
    pairs = tag_pairs if tag_pairs else [(tag_key, tag_val)]
    religion_filter = ''
    if religion:
        religion_filter = f'["religion"="{religion}"]'
    body_lines = []
    for k, v in pairs:
        body_lines.append(f'  node["{k}"="{v}"]{religion_filter}(around:{radius},{lat},{lon});')
        body_lines.append(f'  way["{k}"="{v}"]{religion_filter}(around:{radius},{lat},{lon});')
    body = '\n'.join(body_lines)
    return f'[out:json][timeout:25];\n(\n{body}\n);\nout center {limit};\n'

def build_overpass_bbox(tag_key, tag_val, south, west, north, east, limit, religion=None, tag_pairs=None):
    pairs = tag_pairs if tag_pairs else [(tag_key, tag_val)]
    religion_filter = ''
    if religion:
        religion_filter = f'["religion"="{religion}"]'
    body_lines = []
    for k, v in pairs:
        body_lines.append(f'  node["{k}"="{v}"]{religion_filter}({south},{west},{north},{east});')
        body_lines.append(f'  way["{k}"="{v}"]{religion_filter}({south},{west},{north},{east});')
    body = '\n'.join(body_lines)
    return f'[out:json][timeout:25];\n(\n{body}\n);\nout center {limit};\n'

def parse_overpass_elements(elements, ref_lat=None, ref_lon=None):
    places = []
    for el in elements:
        if el['type'] == 'way':
            center = el.get('center', {})
            el_lat = center.get('lat')
            el_lon = center.get('lon')
        else:
            el_lat = el.get('lat')
            el_lon = el.get('lon')
        if el_lat is None or el_lon is None:
            continue
        tags = el.get('tags', {})
        name = tags.get('name') or tags.get('name:en') or ''
        addr_parts = []
        for part_key in ('addr:housenumber', 'addr:street', 'addr:city'):
            val = tags.get(part_key)
            if val:
                addr_parts.append(val)
        address_str = ', '.join(addr_parts) if addr_parts else ''
        place = {'name': name, 'address': address_str, 'lat': el_lat, 'lon': el_lon, 'osm_type': el.get('type', ''), 'osm_id': el.get('id', ''), 'maps_url': f'https://www.google.com/maps/search/?api=1&query={el_lat},{el_lon}', 'tags': {k: v for k, v in tags.items() if k not in ('name', 'name:en', 'addr:housenumber', 'addr:street', 'addr:city')}}
        for src_key, dst_key in (('cuisine', 'cuisine'), ('opening_hours', 'hours'), ('phone', 'phone'), ('website', 'website')):
            val = tags.get(src_key)
            if val:
                place[dst_key] = val
        if ref_lat is not None and ref_lon is not None:
            dist_m = haversine_m(ref_lat, ref_lon, el_lat, el_lon)
            place['distance_m'] = round(dist_m, 1)
            place['directions_url'] = f'https://www.google.com/maps/dir/?api=1&origin={ref_lat},{ref_lon}&destination={el_lat},{el_lon}'
        places.append(place)
    if places and 'distance_m' in places[0]:
        places.sort(key=lambda p: p['distance_m'])
    return places

def cmd_search(args):
    query = ' '.join(args.query)
    raw = nominatim_search(query, limit=5)
    if not raw:
        print_json({'query': query, 'results': [], 'count': 0, 'data_source': DATA_SOURCE})
        return
    results = []
    for item in raw:
        bb = item.get('boundingbox', [])
        results.append({'name': item.get('name') or item.get('display_name', ''), 'display_name': item.get('display_name', ''), 'lat': float(item['lat']), 'lon': float(item['lon']), 'type': item.get('type', ''), 'category': item.get('category', ''), 'osm_type': item.get('osm_type', ''), 'osm_id': item.get('osm_id', ''), 'bounding_box': {'min_lat': float(bb[0]) if len(bb) > 0 else None, 'max_lat': float(bb[1]) if len(bb) > 1 else None, 'min_lon': float(bb[2]) if len(bb) > 2 else None, 'max_lon': float(bb[3]) if len(bb) > 3 else None}, 'importance': item.get('importance')})
    print_json({'query': query, 'results': results, 'count': len(results), 'data_source': DATA_SOURCE})

def cmd_reverse(args):
    try:
        lat = float(args.lat)
        lon = float(args.lon)
    except ValueError:
        error_exit('LAT and LON must be numeric values.')
    if not -90 <= lat <= 90:
        error_exit('Latitude must be between -90 and 90.')
    if not -180 <= lon <= 180:
        error_exit('Longitude must be between -180 and 180.')
    data = nominatim_reverse(lat, lon)
    if 'error' in data:
        error_exit(f'Reverse geocode failed: {data['error']}')
    address = data.get('address', {})
    print_json({'lat': lat, 'lon': lon, 'display_name': data.get('display_name', ''), 'address': {'house_number': address.get('house_number', ''), 'road': address.get('road', ''), 'neighbourhood': address.get('neighbourhood', ''), 'suburb': address.get('suburb', ''), 'city': address.get('city') or address.get('town') or address.get('village', ''), 'county': address.get('county', ''), 'state': address.get('state', ''), 'postcode': address.get('postcode', ''), 'country': address.get('country', ''), 'country_code': address.get('country_code', '')}, 'osm_type': data.get('osm_type', ''), 'osm_id': data.get('osm_id', ''), 'data_source': DATA_SOURCE})

def cmd_nearby(args):
    if getattr(args, 'near', None):
        near_query = ' '.join(args.near).strip() if isinstance(args.near, list) else str(args.near).strip()
        if not near_query:
            error_exit('--near must be a non-empty address or place name.')
        lat, lon, _ = geocode_single(near_query)
    else:
        try:
            lat = float(args.lat)
            lon = float(args.lon)
        except (TypeError, ValueError):
            error_exit('Provide numeric LAT and LON, or use --near "<address>".')
    categories = []
    if getattr(args, 'category_list', None):
        categories.extend(args.category_list)
    if getattr(args, 'category', None):
        categories.append(args.category)
    categories = list(dict.fromkeys((c.lower() for c in categories if c)))
    if not categories:
        error_exit('Provide at least one category (positional or --category).')
    unknown = [c for c in categories if c not in CATEGORY_TAGS]
    if unknown:
        error_exit(f'Unknown categor{('ies' if len(unknown) > 1 else 'y')} {', '.join((repr(c) for c in unknown))}. Valid categories: {', '.join(VALID_CATEGORIES)}')
    radius = int(args.radius)
    limit = int(args.limit)
    if radius <= 0:
        error_exit('Radius must be a positive integer (metres).')
    if limit <= 0:
        error_exit('Limit must be a positive integer.')
    merged = {}
    for category in categories:
        tag_pairs = _tags_for(category)
        religion = RELIGION_FILTER.get(category)
        query = build_overpass_nearby(None, None, lat, lon, radius, limit, religion=religion, tag_pairs=tag_pairs)
        raw = overpass_query(query)
        elements = raw.get('elements', [])
        for place in parse_overpass_elements(elements, ref_lat=lat, ref_lon=lon):
            place['category'] = category
            key = (place.get('osm_type', ''), place.get('osm_id', ''))
            if key not in merged:
                merged[key] = place
    places = sorted(merged.values(), key=lambda p: p.get('distance_m', float('inf')))[:limit]
    print_json({'center_lat': lat, 'center_lon': lon, 'categories': categories, 'radius_m': radius, 'count': len(places), 'results': places, 'data_source': DATA_SOURCE})

def cmd_distance(args):
    origin_query = ' '.join(args.origin)
    destination_query = ' '.join(args.to)
    mode = args.mode.lower()
    if mode not in OSRM_PROFILES:
        error_exit(f"Invalid mode '{mode}'. Choose from: {', '.join(OSRM_PROFILES)}")
    o_lat, o_lon, o_name = geocode_single(origin_query)
    d_lat, d_lon, d_name = geocode_single(destination_query)
    profile = OSRM_PROFILES[mode]
    url = f'{OSRM_BASE}/{profile}/{o_lon},{o_lat};{d_lon},{d_lat}?overview=false&steps=false'
    osrm_data = http_get(url)
    if osrm_data.get('code') != 'Ok':
        error_exit(f'OSRM routing failed: {osrm_data.get('message', osrm_data.get('code', 'unknown error'))}')
    routes = osrm_data.get('routes', [])
    if not routes:
        error_exit('No route found between the two locations.')
    route = routes[0]
    distance_m = route.get('distance', 0)
    duration_s = route.get('duration', 0)
    distance_km = round(distance_m / 1000, 3)
    duration_min = round(duration_s / 60, 2)
    straight_m = haversine_m(o_lat, o_lon, d_lat, d_lon)
    print_json({'origin': {'query': origin_query, 'display_name': o_name, 'lat': o_lat, 'lon': o_lon}, 'destination': {'query': destination_query, 'display_name': d_name, 'lat': d_lat, 'lon': d_lon}, 'mode': mode, 'distance_km': distance_km, 'distance_m': round(distance_m, 1), 'duration_minutes': duration_min, 'duration_seconds': round(duration_s, 1), 'straight_line_km': round(straight_m / 1000, 3), 'data_source': DATA_SOURCE})

def _format_duration(seconds):
    if seconds < 60:
        return f'{round(seconds)}s'
    minutes = seconds / 60
    if minutes < 60:
        return f'{round(minutes, 1)} min'
    hours = int(minutes // 60)
    remaining = round(minutes % 60)
    return f'{hours}h {remaining}min'

def _format_distance(metres):
    if metres < 1000:
        return f'{round(metres)} m'
    return f'{round(metres / 1000, 2)} km'

def cmd_directions(args):
    origin_query = ' '.join(args.origin)
    destination_query = ' '.join(args.to)
    mode = args.mode.lower()
    if mode not in OSRM_PROFILES:
        error_exit(f"Invalid mode '{mode}'. Choose from: {', '.join(OSRM_PROFILES)}")
    o_lat, o_lon, o_name = geocode_single(origin_query)
    d_lat, d_lon, d_name = geocode_single(destination_query)
    profile = OSRM_PROFILES[mode]
    url = f'{OSRM_BASE}/{profile}/{o_lon},{o_lat};{d_lon},{d_lat}?overview=false&steps=true'
    osrm_data = http_get(url)
    if osrm_data.get('code') != 'Ok':
        error_exit(f'OSRM routing failed: {osrm_data.get('message', osrm_data.get('code', 'unknown error'))}')
    routes = osrm_data.get('routes', [])
    if not routes:
        error_exit('No route found between the two locations.')
    route = routes[0]
    distance_m = route.get('distance', 0)
    duration_s = route.get('duration', 0)
    steps = []
    step_num = 0
    for leg in route.get('legs', []):
        for step in leg.get('steps', []):
            maneuver = step.get('maneuver', {})
            step_dist = step.get('distance', 0)
            step_dur = step.get('duration', 0)
            step_name = step.get('name', '')
            modifier = maneuver.get('modifier', '')
            m_type = maneuver.get('type', '')
            if m_type == 'depart':
                instruction = f'Depart on {step_name}' if step_name else 'Depart'
            elif m_type == 'arrive':
                instruction = 'Arrive at destination'
            elif m_type == 'turn':
                instruction = f'Turn {modifier} onto {step_name}' if step_name else f'Turn {modifier}'
            elif m_type == 'new name':
                instruction = f'Continue onto {step_name}' if step_name else 'Continue'
            elif m_type == 'merge':
                instruction = f'Merge {modifier} onto {step_name}' if step_name else f'Merge {modifier}'
            elif m_type == 'fork':
                instruction = f'Take the {modifier} fork onto {step_name}' if step_name else f'Take the {modifier} fork'
            elif m_type == 'roundabout':
                instruction = f'Enter roundabout, exit onto {step_name}' if step_name else 'Enter roundabout'
            elif m_type == 'rotary':
                instruction = f'Enter rotary, exit onto {step_name}' if step_name else 'Enter rotary'
            elif m_type == 'end of road':
                instruction = f'At end of road, turn {modifier} onto {step_name}' if step_name else f'At end of road, turn {modifier}'
            elif m_type == 'continue':
                instruction = f'Continue {modifier} on {step_name}' if step_name else f'Continue {modifier}'
            elif m_type == 'on ramp':
                instruction = f'Take ramp onto {step_name}' if step_name else 'Take ramp'
            elif m_type == 'off ramp':
                instruction = f'Take exit onto {step_name}' if step_name else 'Take exit'
            else:
                instruction = f'{m_type} {modifier} {step_name}'.strip()
            step_num += 1
            steps.append({'step': step_num, 'instruction': instruction, 'distance': _format_distance(step_dist), 'distance_m': round(step_dist, 1), 'duration': _format_duration(step_dur), 'duration_s': round(step_dur, 1), 'road_name': step_name, 'maneuver': m_type})
    print_json({'origin': {'query': origin_query, 'display_name': o_name, 'lat': o_lat, 'lon': o_lon}, 'destination': {'query': destination_query, 'display_name': d_name, 'lat': d_lat, 'lon': d_lon}, 'mode': mode, 'total_distance': _format_distance(distance_m), 'total_distance_m': round(distance_m, 1), 'total_duration': _format_duration(duration_s), 'total_duration_s': round(duration_s, 1), 'steps': steps, 'step_count': len(steps), 'data_source': DATA_SOURCE})

def cmd_timezone(args):
    try:
        lat = float(args.lat)
        lon = float(args.lon)
    except ValueError:
        error_exit('LAT and LON must be numeric values.')
    if not -90 <= lat <= 90:
        error_exit('Latitude must be between -90 and 90.')
    if not -180 <= lon <= 180:
        error_exit('Longitude must be between -180 and 180.')
    timezone_str = None
    timezone_src = None
    current_time = None
    utc_offset = None
    try:
        params = {'latitude': lat, 'longitude': lon}
        tz_data = http_get(TIMEAPI_BASE, params=params, silent=True)
        if isinstance(tz_data, dict):
            timezone_str = tz_data.get('timeZone')
            current_time = tz_data.get('currentLocalTime')
            offset_info = tz_data.get('currentUtcOffset', {})
            if isinstance(offset_info, dict):
                oh = offset_info.get('hours', 0)
                om = abs(offset_info.get('minutes', 0))
                os_ = offset_info.get('seconds', 0)
                sign = '+' if oh >= 0 else '-'
                utc_offset = f'{sign}{abs(oh):02d}:{om:02d}'
                if os_:
                    utc_offset = f'{utc_offset}:{os_:02d}'
            elif tz_data.get('standardUtcOffset'):
                offset_info2 = tz_data['standardUtcOffset']
                if isinstance(offset_info2, dict):
                    oh = offset_info2.get('hours', 0)
                    om = abs(offset_info2.get('minutes', 0))
                    os_ = offset_info2.get('seconds', 0)
                    sign = '+' if oh >= 0 else '-'
                    utc_offset = f'{sign}{abs(oh):02d}:{om:02d}'
                    if os_:
                        utc_offset = f'{utc_offset}:{os_:02d}'
            timezone_src = 'timeapi.io'
    except (RuntimeError, KeyError, TypeError):
        pass
    if not timezone_str:
        approx_offset_h = round(lon / 15)
        if approx_offset_h >= 0:
            utc_offset = f'+{approx_offset_h:02d}:00'
        else:
            utc_offset = f'-{abs(approx_offset_h):02d}:00'
        timezone_str = f'UTC{utc_offset}'
        timezone_src = 'longitude approximation (longitude/15)'
    print_json({'lat': lat, 'lon': lon, 'timezone': timezone_str, 'utc_offset': utc_offset, 'current_time': current_time, 'source': timezone_src, 'data_source': DATA_SOURCE})

def cmd_bbox(args):
    try:
        lat1 = float(args.lat1)
        lon1 = float(args.lon1)
        lat2 = float(args.lat2)
        lon2 = float(args.lon2)
    except ValueError:
        error_exit('All coordinate arguments must be numeric values.')
    south = min(lat1, lat2)
    north = max(lat1, lat2)
    west = min(lon1, lon2)
    east = max(lon1, lon2)
    category = args.category.lower()
    if category not in CATEGORY_TAGS:
        error_exit(f"Unknown category '{category}'. Valid categories: {', '.join(VALID_CATEGORIES)}")
    limit = int(args.limit)
    if limit <= 0:
        error_exit('Limit must be a positive integer.')
    tag_pairs = _tags_for(category)
    religion = RELIGION_FILTER.get(category)
    query = build_overpass_bbox(None, None, south, west, north, east, limit, religion=religion, tag_pairs=tag_pairs)
    raw = overpass_query(query)
    elements = raw.get('elements', [])
    center_lat = (south + north) / 2
    center_lon = (west + east) / 2
    places = parse_overpass_elements(elements, ref_lat=center_lat, ref_lon=center_lon)
    for p in places:
        p['category'] = category
    print_json({'bounding_box': {'south': south, 'west': west, 'north': north, 'east': east}, 'category': category, 'count': len(places), 'results': places, 'data_source': DATA_SOURCE})

def cmd_area(args):
    query = ' '.join(args.place)
    raw = nominatim_search(query, limit=1)
    if not raw:
        error_exit(f'Could not find place: {query}')
    item = raw[0]
    bb = item.get('boundingbox', [])
    if len(bb) < 4:
        error_exit(f'No bounding box data available for: {query}')
    min_lat = float(bb[0])
    max_lat = float(bb[1])
    min_lon = float(bb[2])
    max_lon = float(bb[3])
    avg_lat = (min_lat + max_lat) / 2
    height_km = haversine_m(min_lat, min_lon, max_lat, min_lon) / 1000
    width_km = haversine_m(avg_lat, min_lon, avg_lat, max_lon) / 1000
    approx_area_km2 = round(height_km * width_km, 3)
    print_json({'query': query, 'display_name': item.get('display_name', ''), 'lat': float(item['lat']), 'lon': float(item['lon']), 'type': item.get('type', ''), 'category': item.get('category', ''), 'bounding_box': {'south': min_lat, 'north': max_lat, 'west': min_lon, 'east': max_lon}, 'dimensions': {'width_km': round(width_km, 3), 'height_km': round(height_km, 3)}, 'approx_area_km2': approx_area_km2, 'osm_type': item.get('osm_type', ''), 'osm_id': item.get('osm_id', ''), 'data_source': DATA_SOURCE})

def build_parser():
    parser = argparse.ArgumentParser(prog='maps_client.py', description='CLI maps tool: geocoding, reverse geocoding, POI search, routing, directions, timezone, and area lookup. Powered by OpenStreetMap, OSRM, Overpass, and TimeAPI.io. No API keys required.', formatter_class=argparse.RawDescriptionHelpFormatter, epilog='Examples:\n  maps_client.py search Times Square\n  maps_client.py reverse 40.758 -73.985\n  maps_client.py nearby 40.758 -73.985 restaurant --radius 800\n  maps_client.py distance New York --to Los Angeles --mode driving\n  maps_client.py directions Paris --to Berlin --mode driving\n  maps_client.py timezone 48.8566 2.3522\n  maps_client.py bbox 40.70 -74.02 40.78 -73.95 restaurant\n  maps_client.py area Manhattan')
    sub = parser.add_subparsers(dest='command', required=True, metavar='COMMAND')
    p_search = sub.add_parser('search', help='Geocode a place name to coordinates.', description='Search for a place by name and return coordinates and details.')
    p_search.add_argument('query', nargs='+', help='Place name or address to search.')
    p_reverse = sub.add_parser('reverse', help='Reverse geocode coordinates to an address.', description='Convert latitude/longitude coordinates to a human-readable address.')
    p_reverse.add_argument('lat', help='Latitude (decimal degrees).')
    p_reverse.add_argument('lon', help='Longitude (decimal degrees).')
    p_nearby = sub.add_parser('nearby', help='Find nearby places of a given category.', description=f'Find points of interest near a location using the Overpass API.\nProvide either LAT/LON, or use --near "<address>" to auto-geocode.\nCategories can be specified positionally OR repeated via --category\nto merge multiple types in one query (e.g. --category bar --category cafe).\nCategories: {', '.join(VALID_CATEGORIES)}', formatter_class=argparse.RawDescriptionHelpFormatter)
    p_nearby.add_argument('lat', nargs='?', default=None, help='Center latitude (decimal degrees). Omit if using --near.')
    p_nearby.add_argument('lon', nargs='?', default=None, help='Center longitude (decimal degrees). Omit if using --near.')
    p_nearby.add_argument('category', nargs='?', default=None, help='POI category (use --help for full list). Omit if using --category flags.')
    p_nearby.add_argument('--near', nargs='+', metavar='PLACE', help='Address, city, or landmark to search around (geocoded via Nominatim).')
    p_nearby.add_argument('--category', action='append', dest='category_list', default=[], metavar='CAT', help='POI category (repeatable — adds a type to the search).')
    p_nearby.add_argument('--radius', '-r', default=500, type=int, metavar='METRES', help='Search radius in metres (default: 500).')
    p_nearby.add_argument('--limit', '-n', default=10, type=int, metavar='N', help='Maximum number of results (default: 10).')
    p_dist = sub.add_parser('distance', help='Calculate road distance and travel time.', description='Calculate road distance and estimated travel time between two places.\nExample: maps_client.py distance New York --to Los Angeles', formatter_class=argparse.RawDescriptionHelpFormatter)
    p_dist.add_argument('origin', nargs='+', help='Origin address or place name.')
    p_dist.add_argument('--to', nargs='+', required=True, metavar='DEST', help='Destination address or place name (required).')
    p_dist.add_argument('--mode', '-m', default='driving', choices=list(OSRM_PROFILES.keys()), help='Travel mode (default: driving).')
    p_dir = sub.add_parser('directions', help='Get turn-by-turn directions between two places.', description='Get step-by-step navigation directions between two places.\nExample: maps_client.py directions Paris --to Berlin --mode driving', formatter_class=argparse.RawDescriptionHelpFormatter)
    p_dir.add_argument('origin', nargs='+', help='Origin address or place name.')
    p_dir.add_argument('--to', nargs='+', required=True, metavar='DEST', help='Destination address or place name (required).')
    p_dir.add_argument('--mode', '-m', default='driving', choices=list(OSRM_PROFILES.keys()), help='Travel mode (default: driving).')
    p_tz = sub.add_parser('timezone', help='Get timezone information for coordinates.', description='Look up timezone and current local time for a lat/lon coordinate.')
    p_tz.add_argument('lat', help='Latitude (decimal degrees).')
    p_tz.add_argument('lon', help='Longitude (decimal degrees).')
    p_bbox = sub.add_parser('bbox', help='Find POIs within a bounding box.', description=f"Search for points of interest within a geographic bounding box.\nTip: use the 'area' command to find bounding boxes for named places.\nCategories: {', '.join(VALID_CATEGORIES)}", formatter_class=argparse.RawDescriptionHelpFormatter)
    p_bbox.add_argument('lat1', help='First corner latitude.')
    p_bbox.add_argument('lon1', help='First corner longitude.')
    p_bbox.add_argument('lat2', help='Second corner latitude.')
    p_bbox.add_argument('lon2', help='Second corner longitude.')
    p_bbox.add_argument('category', help='POI category to search for.')
    p_bbox.add_argument('--limit', '-n', default=20, type=int, metavar='N', help='Maximum number of results (default: 20).')
    p_area = sub.add_parser('area', help='Get bounding box and area info for a named place.', description="Look up a place by name and return its bounding box, dimensions, and approximate area. Useful as input to the 'bbox' command.")
    p_area.add_argument('place', nargs='+', help="Place name to look up (e.g., 'Manhattan' or 'downtown Seattle').")
    return parser

def main():
    parser = build_parser()
    args = parser.parse_args()
    dispatch = {'search': cmd_search, 'reverse': cmd_reverse, 'nearby': cmd_nearby, 'distance': cmd_distance, 'directions': cmd_directions, 'timezone': cmd_timezone, 'bbox': cmd_bbox, 'area': cmd_area}
    handler = dispatch.get(args.command)
    if handler is None:
        error_exit(f'Unknown command: {args.command}')
    handler(args)
if __name__ == '__main__':
    main()
