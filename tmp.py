import re


def is_valid_category_input(value):
    if value == '':
        return True
    elif re.match(r'^[1-4]$', value):
        return True
    elif re.match(r'^[1-4]-[1-4]$', value):
        start, end = map(int, value.split('-'))
        return start < end
    return False


def is_valid_reload_time(value):
    if value == '':
        return True
    elif re.match(r'^\d+-\d+$', value):
        start, end = map(int, value.split('-'))
        return start < end
    return False


def get_valid_input(prompt, validation_func, default=''):
    while True:
        value = input(prompt).strip()
        if validation_func(value):
            return value if value else default
        print("Неправильне введення. Будь ласка, введіть одну цифру (1-4), діапазон (наприклад, 1-4) або залиште порожнім.")


def parse_reload_time(value):
    if value:
        start, end = map(int, value.split('-'))
        return [start, end]
    return [45, 60]


def gather_inputs():
    username = input('username: ').strip()
    password = input('password: ').strip()
    proxy = input('proxy: ').strip() if not adspower_link else None
    reload_time_input = get_valid_input('Reload time (Або залиште порожнім для [45, 60]): ', is_valid_reload_time, '45-60')
    reload_time = parse_reload_time(reload_time_input)
    
    data = []
    for row_index in row_indexes:
        match = matches[int(row_index)-1][0]
        print(match, "[НАЛАШТУВАННЯ]")

        categories = {}
        for i in range(1, 5):
            category_value = get_valid_input(f'Category {i} (Або залиште порожнім): ', is_valid_category_input)
            categories[f"Category {i}"] = category_value
        
        if input('Use same values for Restricted View categories? [yes/no]: ').strip().lower() == 'yes':
            for i in range(1, 5):
                categories[f"Cat. {i} Restricted View"] = categories[f"Category {i}"]
        else:
            for i in range(1, 5):
                categories[f"Cat. {i} Restricted View"] = get_valid_input(f'Cat. {i} Restricted View (Або залиште порожнім): ', is_valid_category_input)

        categories["Fans First"] = get_valid_input('Fans First (Або залиште порожнім): ', is_valid_category_input)
        categories["Prime Seats"] = get_valid_input('Prime Seats (Або залиште порожнім): ', is_valid_category_input)

        data.append([match, categories])
    return data, username, password, proxy, reload_time


if __name__ == '__main__':
    # data = get_data_from_google_sheets()
    threads = []
    matches = [
        ["Germany vs Scotland"],
        ["Hungary vs Switzerland"],
        ["Spain vs Croatia"],
        ["Italy vs Albania"],
        ["Serbia vs England"],
        ["Slovenia vs Denmark"],
        ["Poland vs Netherlands"],
        ["Austria vs France"],
        ["Belgium vs Slovakia"],
        ["Romania vs Ukraine"],
        ["Turkey vs Georgia"],
        ["Portugal vs Czech Republic"],
        ["Scotland vs Switzerland"],
        ["Germany vs Hungary"],
        ["Croatia vs Albania"],
        ["Spain vs Italy"],
        ["Denmark vs England"],
        ["Slovenia vs Serbia"],
        ["Poland vs Austria"],
        ["Netherlands vs France"],
        ["Slovakia vs Ukraine"],
        ["Belgium vs Romania"],
        ["Turkey vs Portugal"],
        ["Georgia vs Czechia"],
        ["Switzerland vs Germany"],
        ["Scotland vs Hungary"],
        ["Albania vs Spain"],
        ["Croatia vs Italy"],
        ["England vs Slovenia"],
        ["Denmark vs Serbia"],
        ["Netherlands vs Austria"],
        ["France vs Poland"],
        ["Slovakia vs Romania"],
        ["Ukraine vs Belgium"],
        ["Georgia vs Portugal"],
        ["Czech Republic vs Turkey"],
        ["1A vs 2C"],
        ["2A vs 2B"],
        ["1B vs 3A/D/E/F"],
        ["1C vs 3D/E/F"],
        ["1F vs 3A/B/C"],
        ["2D vs 2E"],
        ["1E vs 3A/B/C/D"],
        ["W39 vs W37"],
        ["W40 vs W38"],
        ["W41 vs W42"],
        ["W43 vs W44"],
        ["W45 vs W46"],
        ["W47 vs W48"],
        ["W49 vs W50"]
    ]
    
    for index, match in enumerate(matches, 1):
        print(f"{index}: {match[0]}")
    data = []
    row_indexes= input('Indexes (separated by + symbol): ').strip().split('+')


    while True:
        is_adspower = input('use adspower? [ yes / no ]: ').strip().lower()
        if is_adspower in ['yes', 'no']:
            adspower_link = None
            if is_adspower == 'yes':
                adspower = input('adspower api: ').strip()
                adspower_id = input('adspower id: ').strip()
                adspower_link = f"{adspower}/api/v1/browser/start?user_id={adspower_id}"
                print(adspower_link)

            data, username, password, proxy, reload_time = gather_inputs()
            print(data, 'data')
        else:
            print('Введіть 1 з запропонованих варіантів [ yes / no ]')