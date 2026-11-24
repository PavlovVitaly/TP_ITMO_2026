import statistics
from dataclasses import dataclass, field
from datetime import date, datetime
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
    """Способ получения базовой ставки аренды."""
    EXACT = "EXACT"
    DISTRICT = "DISTRICT"


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
    """Результат аналитической оценки конкретного объекта."""
    id: int
    advertisement: AssetAdvertisement
    calculated_roi: float | None
    base_rent_rate: int | None
    calculation_method: CalculationMethod | None


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
    """Исключение при отсутствии объектов под заданный бюджет."""
    pass


def _same_text(left: str, right: str) -> bool:
    """Сравнивает текст без учета регистра."""
    return left.lower() == right.lower()


class AdvertisementRepository:
    """Инкапсулирует хранение и выборку объявлений об активах."""

    def __init__(self, storage: list[AssetAdvertisement]) -> None:
        self._storage = storage

    def get_sale_ads_by_criteria(
        self, budget: int, city: str, district: str, street: str | None = None
    ) -> list[AssetAdvertisement]:
        """Возвращает объявления продажи под заданный бюджет и адрес."""
        result = []
        for ad in self._storage:
            if not ad.category.is_available_in_mvp:
                continue
            if ad.deal_type != DealType.SALE or ad.price > budget:
                continue
            if not _same_text(ad.city, city) or not _same_text(ad.district, district):
                continue
            if street and not _same_text(ad.street, street):
                continue
            result.append(ad)
        return result

    def get_rent_ads_in_building(
        self,
        city: str,
        district: str,
        street: str,
        house_number: str | None,
        category_id: int,
    ) -> list[AssetAdvertisement]:
        """Ищет аренду в том же городе, районе, доме и категории."""
        if not house_number:
            return []
        return [
            ad for ad in self._storage
            if ad.deal_type == DealType.RENT
            and ad.category.id == category_id
            and _same_text(ad.city, city)
            and _same_text(ad.district, district)
            and _same_text(ad.street, street)
            and ad.house_number == house_number
        ]

    def get_rent_ads_in_district(
        self, city: str, district: str, category_id: int
    ) -> list[AssetAdvertisement]:
        """Ищет аренду в том же городе и районе; это не георадиус."""
        return [
            ad for ad in self._storage
            if ad.deal_type == DealType.RENT
            and ad.category.id == category_id
            and _same_text(ad.city, city)
            and _same_text(ad.district, district)
        ]


class ROIScoringService:
    """Оценивает доходность и создает аналитические элементы."""

    def __init__(self, ad_repo: AdvertisementRepository) -> None:
        self._ad_repo = ad_repo
        self._item_counter = 1

    def _calculate_median_rent(
        self, rent_ads: list[AssetAdvertisement]
    ) -> int | None:
        """Возвращает медианную ставку или None, если выборка пуста."""
        if not rent_ads:
            return None
        prices = [ad.price for ad in rent_ads]
        return round(statistics.median(prices))

    def _estimate_base_rent(
        self, ad: AssetAdvertisement
    ) -> tuple[int | None, CalculationMethod | None]:
        """Сначала ищет точный аналог, затем использует объявления района."""
        exact_rent_ads = self._ad_repo.get_rent_ads_in_building(
            ad.city,
            ad.district,
            ad.street,
            ad.house_number,
            ad.category.id,
        )
        if exact_rent_ads:
            return (
                self._calculate_median_rent(exact_rent_ads),
                CalculationMethod.EXACT,
            )

        district_rent_ads = self._ad_repo.get_rent_ads_in_district(
            ad.city, ad.district, ad.category.id
        )
        district_rate = self._calculate_median_rent(district_rent_ads)
        if district_rate is None:
            return None, None
        return district_rate, CalculationMethod.DISTRICT

    def evaluate_asset(self, ad: AssetAdvertisement) -> DigestAnalyticalItem:
        """Оценивает объявление; при отсутствии аренды ROI остается None."""
        base_rent_rate, method = self._estimate_base_rent(ad)
        if base_rent_rate is None:
            calculated_roi = None
        elif ad.price > 0:
            calculated_roi = round((base_rent_rate * 12 / ad.price) * 100, 2)
        else:
            calculated_roi = 0.0

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
    """Координирует поиск, оценку и сортировку объектов."""

    def __init__(
        self, ad_repo: AdvertisementRepository, roi_analyzer: ROIScoringService
    ) -> None:
        self._ad_repo = ad_repo
        self._roi_analyzer = roi_analyzer

    def _sort_items_by_roi(
        self, items: list[DigestAnalyticalItem]
    ) -> list[DigestAnalyticalItem]:
        """Сортирует рассчитанные ROI по убыванию, неоцененные — в конец."""
        return sorted(
            items,
            key=lambda item: (
                item.calculated_roi is not None,
                item.calculated_roi if item.calculated_roi is not None else 0.0,
            ),
            reverse=True,
        )

    def find_profitable_assets(
        self,
        current_user: User,
        budget: int,
        city: str,
        district: str,
        street: str | None = None,
    ) -> list[DigestAnalyticalItem]:
        """Ищет подходящие объекты и возвращает их по убыванию ROI."""
        sale_ads = self._ad_repo.get_sale_ads_by_criteria(
            budget, city, district, street
        )
        if not sale_ads:
            raise EmptyResultException(
                "По вашему бюджету ничего не найдено. Увеличьте сумму или выберите другой регион."
            )

        evaluated_items = [self._roi_analyzer.evaluate_asset(ad) for ad in sale_ads]
        return self._sort_items_by_roi(evaluated_items)


if __name__ == "__main__":
    real_estate_cat = AssetCategory(
        id=1, name="Жилая недвижимость", is_available_in_mvp=True
    )
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
            if item.calculated_roi is None:
                rent_text = "данных об аренде нет"
                roi_text = "ROI не рассчитан"
                method_text = ""
            else:
                rent_text = f"аренда: {item.base_rent_rate:,} руб./мес."
                method_text = (
                    " (точные данные)"
                    if item.calculation_method == CalculationMethod.EXACT
                    else " (оценка по району)"
                )
                roi_text = f"ROI: {item.calculated_roi}%{method_text}"
            print(
                f"Объект #{ad.id} ({ad.street}, д. {ad.house_number}) | "
                f"Цена: {ad.price:,} руб. | {rent_text} | {roi_text}"
            )
    except EmptyResultException as e:
        print(f"Ошибка: {e}")

    print("\n--- Сценарий 2: Недостаточный бюджет 1 000 000 руб. ---")
    try:
        controller.find_profitable_assets(
            current_user=investor,
            budget=1_000_000,
            city="Санкт-Петербург",
            district="Приморский",
        )
    except EmptyResultException as e:
        print(f"Перехвачено исключение: {e}")
