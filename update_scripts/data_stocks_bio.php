<?php
/**
 * Обновление остатков и цен по артикулу (PROPERTY_CODE) из входного JSON.
 * Главное изменение: не удаляем BASE, используем upsert цен.
 */

require($_SERVER["DOCUMENT_ROOT"]."/bitrix/modules/main/include/prolog_before.php");

global $USER;
if (!is_object($USER)) {
    $USER = new CUser;
}
$USER->Authorize(1);

use Bitrix\Main\Loader;
use Bitrix\Catalog\ProductTable;
use Bitrix\Catalog\PriceTable;

Loader::includeModule("iblock");
Loader::includeModule("catalog");

// ---------- helpers ----------
/**
 * upsertPrice - обновить или создать цену.
 */
function upsertPrice(int $productId, int $catalogGroupId, float $price, string $currency = 'KZT'): void
{
    $exist = \Bitrix\Catalog\PriceTable::getList([
        'filter' => ['PRODUCT_ID' => $productId, 'CATALOG_GROUP_ID' => $catalogGroupId],
        'select' => ['ID']
    ])->fetch();

    $fields = [
        'PRODUCT_ID'       => $productId,
        'CATALOG_GROUP_ID' => $catalogGroupId,
        'PRICE'            => $price,
        'CURRENCY'         => $currency,
        'PRICE_SCALE'      => $price,
    ];

    if ($exist) {
        $res = \Bitrix\Catalog\PriceTable::update($exist['ID'], $fields);
    } else {
        $res = \Bitrix\Catalog\PriceTable::add($fields);
    }

    if (!$res->isSuccess()) {
        throw new \Exception(implode(', ', $res->getErrorMessages()));
    }
}

/**
 * deletePriceForType - удалить цену только для указанного типа.
 */
function deletePriceForType(int $productId, int $catalogGroupId): void
{
    $iter = \Bitrix\Catalog\PriceTable::getList([
        'filter' => ['PRODUCT_ID' => $productId, 'CATALOG_GROUP_ID' => $catalogGroupId],
        'select' => ['ID']
    ]);
    while ($row = $iter->fetch()) {
        \Bitrix\Catalog\PriceTable::delete($row['ID']);
    }
}

// ---------- входные данные ----------
$inputJSON = file_get_contents('php://input');
$data = json_decode($inputJSON, true);

if (!$data || !isset($data['stocks']) || !is_array($data['stocks'])) {
    http_response_code(400);
    echo json_encode([
        'status'  => 'error',
        'message' => 'Некорректные данные: отсутствует массив "stocks".'
    ], JSON_UNESCAPED_UNICODE);
    exit;
}

$result = [];

// ---------- настройки ----------
$IBLOCK_ID = 18;

// Типы цен (проверь ID у себя!)
$priceTypeIds = [
    'BASE'  => 1, // базовая (розничная) — видна гостям
    'pz8'   => 3, // Под заказ 8 дней
    'pz8cu' => 6, // Под заказ 8 дней (цену уточняйте)
    'pz'    => 7, // Под заказ
];

// ---------- обработка ----------
foreach ($data['stocks'] as $item) {
    $code    = $item['code']    ?? '';
    $inStock = (int)($item['inStock'] ?? 0);
    $price   = (float)($item['price']   ?? 0);

    if (!$code) {
        $result[] = ['status' => 'error', 'message' => 'Отсутствует артикул (code).'];
        continue;
    }

    // Найти товар по PROPERTY_CODE
    $res = CIBlockElement::GetList(
        ['ID' => 'ASC'],
        ['IBLOCK_ID' => $IBLOCK_ID, 'PROPERTY_CODE' => $code],
        false,
        ['nTopCount' => 1],
        ['ID', 'NAME']
    );

    if (!($product = $res->Fetch())) {
        $result[] = ['status' => 'error', 'message' => "Товар с артикулом '{$code}' не найден."];
        continue;
    }

    $productId   = (int)$product['ID'];
    $productName = (string)$product['NAME'];

    // Обновить остаток
    ProductTable::update($productId, ['QUANTITY' => $inStock]);

    // Логика наличия → статус + служебный тип цены
    if ($inStock > 0 && $price > 0) {
        $availabilityStatus = 'Под заказ 8 дней';
        $mainPriceTypeKey   = 'pz8';
    } else {
        $availabilityStatus = 'Под заказ';
        $mainPriceTypeKey   = 'pz';
    }

    // Свойство AVAILABILITY (по коду)
    CIBlockElement::SetPropertyValuesEx($productId, $IBLOCK_ID, [
        'AVAILABILITY' => ['VALUE' => $availabilityStatus]
    ]);

    // Цены
    try {
        // 1) BASE — чтобы цена отображалась на витрине
        if ($price > 0) {
            upsertPrice($productId, $priceTypeIds['BASE'], $price);
        } else {
            // Если цена 0 — скроем цену на карточке, удалив только BASE
            deletePriceForType($productId, $priceTypeIds['BASE']);
        }

        // 2) Служебный тип (pz/pz8) — по твоей логике
        $typeId = $priceTypeIds[$mainPriceTypeKey];
        upsertPrice($productId, $typeId, $price);

        error_log("✅ {$code}: BASE=" . ($price > 0 ? $price : '—') . ", {$mainPriceTypeKey}={$price}");
    } catch (\Exception $e) {
        error_log("❌ {$code}: ошибка цен — " . $e->getMessage());
    }

    // Кеши/индексы
    BXClearCache(true, "/bitrix/catalog.price/");
    BXClearCache(true, "/bitrix/catalog.element/{$productId}");
    CBitrixComponent::clearComponentCache("bitrix:catalog");
    CBitrixComponent::clearComponentCache("bitrix:catalog.section");
    CBitrixComponent::clearComponentCache("bitrix:catalog.element");

    CIBlockElement::UpdateSearch($productId);
    \Bitrix\Iblock\PropertyIndex\Manager::updateElementIndex($IBLOCK_ID, $productId);

    $result[] = [
        'status'        => 'success',
        'product_id'    => $productId,
        'code'          => $code,
        'name'          => $productName,
        'inStock'       => $inStock,
        'price'         => $price,
        'availability'  => $availabilityStatus,
        'mainPriceType' => $mainPriceTypeKey
    ];
}

// Итог
echo json_encode($result, JSON_UNESCAPED_UNICODE);
