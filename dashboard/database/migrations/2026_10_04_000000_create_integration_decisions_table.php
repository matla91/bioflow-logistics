<?php

declare(strict_types=1);

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    public function up(): void
    {
        Schema::create('integration_decisions', function (Blueprint $table): void {
            $table->id();
            $table->char('assessment_id', 64)->unique();
            $table->char('input_sha256', 64);
            $table->string('model_version');
            $table->string('scenario');
            $table->string('external_shipment_id');
            $table->string('recommended_action');
            $table->string('verdict');
            $table->string('selected_action');
            $table->foreignId('user_id')->constrained();
            $table->string('role');
            $table->text('reason');
            $table->json('assessment_snapshot');
            $table->timestamp('decided_at');
            $table->timestamps();

            $table->index(['scenario', 'external_shipment_id', 'decided_at']);
        });
    }

    public function down(): void
    {
        Schema::dropIfExists('integration_decisions');
    }
};
