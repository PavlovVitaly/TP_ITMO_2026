import statistics
from dataclasses import dataclass, field
from enum import Enum


class DealType(Enum):
    """Перечисление направлений сделок в объявлениях."""
    SALE = "SALE"
    RENT = "RENT"


class UserRole(Enum):
    """Перечисление ролей пользователей системы."""
    INVESTOR = "INVESTOR"
    MODERATOR = "MODERATOR"


class CalculationMethod(Enum):
    """Перечисление методов расчета базовой арендной ставки."""
    EXACT = "EXACT"
    RADIUS_500M = "RADIUS_500M"


@dataclass
class AssetCategory:
    """Категория доходного актива."""
    id: int
    name: str
    is_available_in_mvp: bool


@dataclass
class AssetAdvertisement:
    """Объявление о продаже или сдаче в аренду объекта."""
    id: int
    category: AssetCategory
    deal_type: DealType
    price: int
    city: str
    district: str
    street: str
    house_number: str | None
    parsed_at: datetime


@dataclass
class DigestAnalyticalItem:
    """Результат аналитической оценки окупаемости конкретного объекта."""
    id: int
    advertisement: AssetAdvertisement
    calculated_roi: float
    base_rent_rate: int
    calculation_method: CalculationMethod


@dataclass
class SavedSearch:
    """Сохраненный поисковый фильтр пользователя для ежедневного мониторинга."""
    id: int
    max_budget: int
    city: str
    district: str
    street: str | None = None
    is_monitoring_active: bool = True


@dataclass
class DailyDigest:
    """Ежедневный аналитический отчет с подборкой доходных объектов."""
    id: int
    formation_date: date
    	is_viewed: bool = False
    items: list[DigestAnalyticalItem] = field(default_factory=list)


@dataclass
class User:
    """Учетная запись пользователя платформы YieldRadar."""
    id: int
    email: str
    role: UserRole
    saved_searches: list[SavedSearch] = field(default_factory=list)
    digests: list[DailyDigest] = field(default_factory=list)


class EmptyResultException(Exception):
    """Исключение, выбрасываемое при отсутствии объектов под заданный бюджет."""
    pass


class AdvertisementRepository:
    """Инкапсулирует хранение и выборку объектов AssetAdvertisement."""

    def __init__(self, storage: list[AssetAdvertisement]) -> None:
        self._storage = storage

    def get_sale_ads_by_criteria(
        self, budget: int, city: str, district: str, street: str | None = None
    ) -> list[AssetAdvertisement]:
        """Возвращает объявления о продаже, соответствующие бюджету и локации."""
        result = []
        for ad in self._storage:
            if not ad.category.is_available_in_mvp:
                continue
            if ad.deal_type != DealType.SALE or ad.price > budget:
                continue
            if ad.city.lower() != city.lower() or ad.district.lower() != district.lower():
                continue
            if street and ad.street.lower() != street.lower():
                continue
            result.append(ad)
        return result

    def get_rent_ads_in_building(
        self, city: str, street: str, house_number: str | None
    ) -> list[AssetAdvertisement]:
        """Ищет объявления об аренде в конкретном доме."""
        if not house_number:
            return []
        return [
            ad for ad in self._storage
            if ad.deal_type == DealType.RENT
            and ad.city.lower() == city.lower()
            and ad.street.lower() == street.lower()
            and ad.house_number == house_number
        ]

    def get_rent_ads_in_radius_500m(
        self, city: str, district: str, street: str
    ) -> list[AssetAdvertisement]:
        """Ищет объявления об аренде в радиусе 500 метров (по району в MVP)."""
        return [
            ad for ad in self._storage
            if ad.deal_type == DealType.RENT
            and ad.city.lower() == city.lower()
            and ad.district.lower() == district.lower()
        ]


class ROIScoringService:
    """Содержит бизнес-логику оценки доходности и создания DigestAnalyticalItem."""

    def __init__(self, ad_repo: AdvertisementRepository) -> None:
        self._ad_repo = ad_repo
        self._item_counter = 1

    def _calculate_median_rent(self, rent_ads: list[AssetAdvertisement]) -> int:
        """Вычисляет медианную ставку аренды с округлением до целого числа."""
        if not rent_ads:
            return 0
        prices = [ad.price for ad in rent_ads]
        return round(statistics.median(prices))

    def evaluate_asset(self, ad: AssetAdvertisement) -> DigestAnalyticalItem:
        """Оценивает объект продажи и формирует аналитический элемент с ROI."""
        exact_rent_ads = self._ad_repo.get_rent_ads_in_building(
            ad.city, ad.street, ad.house_number
        )

        if exact_rent_ads:
            base_rent_rate = self
            ._calculate_median_rent(exact_rent_ads)
            method = CalculationMethod.EXACT
        else:
            nearby_rent_ads = self._ad_repo.get_rent_ads_in_radius_500m(
                ad.city, ad.district, ad.street
            )
            base_rent_rate = self._calculate_median_rent(nearby_rent_ads)
            method = CalculationMethod.RADIUS_500M

        calculated_roi = round((base_rent_rate * 12 / ad.price) * 100, 2) if ad.price > 0 else 0.0

        item = DigestAnalyticalItem(
            id=self._item_counter,
            advertisement=ad,
            calculated_roi=calculated_roi,
            base_rent_rate=base_rent_rate,
            calculation_method=method,
        )
        self._item_counter += 1
        return item


class SearchController:
    """Координирует сценарий поиска и взаимодействия объектов."""

    def __init__(
        self, ad_repo: AdvertisementRepository, roi_analyzer: ROIScoringService
    ) -> None:
        self._ad_repo = ad_repo
        self._roi_analyzer = roi_analyzer

    def _sort_items_by_roi(
        self, items: list[DigestAnalyticalItem]
    ) -> list[DigestAnalyticalItem]:
        """Сортирует оцененные объекты по убыванию годового ROI."""
        return sorted(items, key=lambda item: item.calculated_roi, reverse=True)

    def find_profitable_assets(
        self,
        current_user: User,
        budget: int,
        city: str,
        district: str,
        street: str | None = None,
    ) -> list[DigestAnalyticalItem]:
        """Выполняет поиск объектов под бюджет и возвращает отсортированный список по доходности."""
        sale_ads = self._ad_repo.get_sale_ads_by_criteria(budget, city, district, street)

        if not sale_ads:
            raise EmptyResultException(
                "По вашему бюджету ничего не найдено. Увеличьте сумму или выберите другой регион."
            )

        evaluated_items: list[DigestAnalyticalItem] = []
        for ad in sale_ads:
            item = self._roi_analyzer.evaluate_asset(ad)
            evaluated_items.append(item)

        return self._sort_items_by_roi(evaluated_items)


if __name__ == "__main__":
    real_estate_cat = AssetCategory(id=1, name="Жилая недвижимость", is_available_in_mvp=True)
    now = datetime.now()

    mock_database = [
        AssetAdvertisement(1, real_estate_cat, DealType.SALE, 6_000_000, "Санкт-Петербург", "Приморский", "Савушкина", "10", now),
        AssetAdvertisement(2, real_estate_cat, DealType.SALE, 5_000_000, "Санкт-Петербург", "Приморский", "Савушкина", "25", now),
        AssetAdvertisement(3, real_estate_cat, DealType.SALE, 15_000_000, "Санкт-Петербург", "Приморский", "Савушкина", "5", now),
        AssetAdvertisement(101, real_estate_cat, DealType.RENT, 35_000, "Санкт-Петербург", "Приморский", "Савушкина", "10", now),
        AssetAdvertisement(102, real_estate_cat, DealType.RENT, 45_000, "Санкт-Петербург", "Приморский", "Савушкина", "10", now),
        AssetAdvertisement(103, real_estate_cat, DealType.RENT, 50_000, "Санкт-Петербург", "Приморский", "Туристская", "12", now),
    ]

    repo = AdvertisementRepository(storage=mock_database)
    analyzer = ROIScoringService(ad_repo=repo)
    controller = SearchController(ad_repo=repo, roi_analyzer=analyzer)

    investor = User(id=1, email="investor@yieldradar.ru", role=UserRole.INVESTOR)

    print("--- Сценарий 1: Успешный поиск с бюджетом 7 000 000 руб. ---")
    try:
        results = controller.find_profitable_assets(
            current_user=investor,
            budget=7_000_000,
            city="Санкт-Петербург",
            district="Приморский",
            street="Савушкина",
        )
        for item in results:
            ad = item.advertisement
            warning = " [Внимание: Расчет приблизительный!]" if item.calculation_method == CalculationMethod.RADIUS_500M else ""
            print()
                f"Объект #{ad.id} ({ad.street}, д. {ad.house_number}) | "
                f"Цена: {ad.price:,} руб. | Аренда: {item.base_rent_rate:,} руб./мес. | "
                f"ROI: {item.calculated_roi}% ({item.calculation_method.value}){warning}"
            )
    except EmptyResultException as e:
        print(f"Ошибка: {e}")

    print("\n--- Сценарий 2: Исключение ID 105 (Недостаточный бюджет 1 000 000 руб.) ---")
    try:
        controller.find_profitable_assets(
            current_user=investor,
            budget=1_000_000,
            city="Санкт-Петербург",
            district="Приморский",
        )
    except EmptyResultException as e:
        print(f"Перехвачено исключение: {e}")

