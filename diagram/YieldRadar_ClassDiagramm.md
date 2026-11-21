classDiagram
    direction TB

    class DealType {
        <<Enumeration>>
        SALE : str
        RENT : str
    }

    class UserRole {
        <<Enumeration>>
        INVESTOR : str
        MODERATOR : str
    }

    class CalculationMethod {
        <<Enumeration>>
        EXACT : str
        RADIUS_500M : str
    }

    class AssetCategory {
        +int id
        +str name
        +bool is_available_in_mvp
    }

    class AssetAdvertisement {
        +int id
        +DealType deal_type
        +Decimal price
        +str city
        +str district
        +str street
        +str | None house_number
        +datetime parsed_at
    }

    class User {
        +int id
        +str email
        +UserRole role
        +list[SavedSearch] saved_searches
        +list[DailyDigest] digests
    }

    class SavedSearch {
        +int id
        +Decimal max_budget
        +str city
        +str district
        +str | None street
        +bool is_monitoring_active
    }

    class DailyDigest {
        +int id
        +date formation_date
        +bool is_viewed
        +list[DigestAnalyticalItem] items
    }

    class DigestAnalyticalItem {
        +int id
        +float calculated_roi
        +Decimal base_rent_rate
        +CalculationMethod calculation_method
    }

    %% Отношения между классами
    AssetCategory "1" --> "0..*" AssetAdvertisement : classifies
    User "1" --o "0..*" SavedSearch : configures
    User "1" --> "0..*" DailyDigest : receives
    DailyDigest "1" *-- "1..*" DigestAnalyticalItem : contains
    DigestAnalyticalItem "1" --> "1" AssetAdvertisement : evaluates

