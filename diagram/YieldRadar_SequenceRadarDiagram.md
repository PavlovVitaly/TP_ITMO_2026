sequenceDiagram
    autonumber
    actor Investor as Начинающий / Pro инвестор
    participant System as Система YieldRadar (MVP)
    participant GeoAPI as Внешний сервис гео-подсказок

    %% Этап 1: Выбор категории и ввод адреса
    Investor->>System: Выбрать категорию актива (category)
    alt Категория != "Жилая недвижимость" [ID 101]
        System-->>Investor: Отобразить заглушку "Раздел находится в разработке" [UC8]
    else Категория == "Жилая недвижимость"
        System-->>Investor: Активировать форму поиска недвижимости

        Investor->>System: Ввести бюджет, выбрать город и начать ввод улицы (query)
        System->>GeoAPI: Запросить подсказки адресов (city, query)
        GeoAPI-->>System: Вернуть список валидных улиц/районов
        System-->>Investor: Отобразить выпадающий список автокомплита [ID 102]

        %% Этап 2: Запуск поиска и расчет ROI
        Investor->>System: Подтвердить адрес и нажать "Поиск" (budget, city, district, street)
        
        alt Объекты продажи <= budget не найдены [ID 105]
            System-->>Investor: Вывести сообщение "По вашему бюджету ничего не найдено" [UC7]
        else Объекты найдены
            loop Для каждого найденного объекта продажи
                alt Есть данные аренды в этом же доме
                    System->>System: Рассчитать ROI (метод EXACT)
                else Нет данных аренды в доме [ID 104]
                    System->>System: Рассчитать медианную аренду в радиусе 500м (метод RADIUS_500M)
                end
            end
            System->>System: Отсортировать объекты по убыванию ROI
            System-->>Investor: Вернуть список объектов с ROI и пометкой точности расчета [UC3, UC6]
        end
    end

