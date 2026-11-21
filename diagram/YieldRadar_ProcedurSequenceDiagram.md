sequenceDiagram
    autonumber
    actor User as Пользователь (UI)
    participant Main as search_profitable_assets()
    participant Filter as filter_sale_ads()
    participant RentCalc as get_estimated_rent()
    participant Median as calculate_median()
    participant RoiCalc as compute_roi_percent()
    participant Sorter as sort_results_by_roi()

    User->>+Main: вызов(budget : int, city : str, district : str, street : str | None, all_ads : list[dict])
    
    %% Шаг 1: Фильтрация объявлений о продаже
    Main->>+Filter: вызов(all_ads, budget, city, district, street)
    Filter-->>-Main: sale_ads : list[dict]

    alt len(sale_ads) == 0 [Исключение ID 105]
        Main-->>User: return {"status": "empty", "msg": "Недостаточный бюджет"}
    else len(sale_ads) > 0
        %% Шаг 2: Цикл обработки каждого найденного объекта
        loop Для каждого ad в sale_ads
            Main->>+RentCalc: вызов(ad : dict, all_ads : list[dict])
            
            %% Вложенный вызов для расчета медианы
            RentCalc->>+Median: вызов(rent_prices : list[int])
            Median-->>-RentCalc: median_rent : int
            
            RentCalc-->>-Main: (base_rent : int, method : str)

            %% Шаг 3: Расчет процента окупаемости
            Main->>+RoiCalc: вызов(sale_price : int, monthly_rent : int)
            RoiCalc-->>-Main: roi_percent : float
        end

        %% Шаг 4: Сортировка итогового списка
        Main->>+Sorter: вызов(evaluated_ads : list[dict])
        Sorter-->>-Main: sorted_ads : list[dict]

        Main-->>-User: return {"status": "ok", "data": sorted_ads}
    end

