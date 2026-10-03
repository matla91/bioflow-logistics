<?php

declare(strict_types=1);

use App\Http\Controllers\DashboardController;
use App\Http\Controllers\IntegrationController;
use App\Http\Controllers\ShipmentController;
use App\Http\Controllers\ShipmentDecisionController;
use Illuminate\Support\Facades\Route;

Route::redirect('/', '/login')->name('home');

Route::middleware(['auth', 'verified'])->group(function () {
    Route::get('dashboard', DashboardController::class)->name('dashboard');
    Route::get('integration', IntegrationController::class)->name('integration');
    Route::get('shipments', [ShipmentController::class, 'index'])->name('shipments.index');
    Route::get('shipments/{shipment}', [ShipmentController::class, 'show'])->name('shipments.show');
    Route::post('shipments/{shipment}/decisions', [ShipmentDecisionController::class, 'store'])->name('shipments.decisions.store');
    Route::delete('shipments/{shipment}/decisions', [ShipmentDecisionController::class, 'destroy'])->name('shipments.decisions.destroy');
});

require __DIR__.'/settings.php';
